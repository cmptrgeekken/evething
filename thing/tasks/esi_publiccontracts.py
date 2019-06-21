# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import datetime
import time

from decimal import Decimal

from .apitask import APITask
import json

from thing.models import Alliance, Character, CharacterApiScope, PublicContract, PublicContractItem, Corporation, Event, Item, Station, APIKey, UserProfile, Region

from multiprocessing import Pool, Value, Array


class EsiPublicContracts(APITask):
    name = 'thing.esi_publiccontracts'

    public_contract_url = 'https://esi.evetech.net/latest/contracts/public/%s/?datasource=tranquility&page=%s'
    public_contract_item_url = 'https://esi.evetech.net/latest/contracts/public/items/%s/?datasource=tranquility'

    def run(self):
        self.init()

        for region in Region.objects.all():
            if region is not None:
                self.import_contracts(region.id)

    def import_contracts(self, region_id):
        now = datetime.datetime.now()

        c_filter = PublicContract.objects.filter(region_id=region_id)

        contracts = []

        page = 1

        ttl_pages = None

        while ttl_pages is None or page <= ttl_pages:
            success, data, headers = self.fetch_esi_url(self.public_contract_url % (region_id,  page), None, headers_to_return=['x-pages'])

            if not success:
                # Failed to retrieve contract information, back out
                print('Import failed: %s' % data)
                return False

            if 'x-pages' in headers:
                ttl_pages = int(headers['x-pages'])
            else:
                ttl_pages = 1

            r_contracts = json.loads(data)

            if len(r_contracts) == 0:
                break

            contracts.extend(r_contracts)

            page += 1

        # First we need to get all of the acceptor and assignee IDs
        contract_ids = set()
        station_ids = set()
        lookup_ids = set()
        lookup_corp_ids = set()
        contract_rows = []

        for row in contracts:
            contract_ids.add(int(row['contract_id']))

            if 'start_location_id' in row:
                station_ids.add(int(row['start_location_id']))

            if 'end_location_id' in row:
                station_ids.add(int(row['end_location_id']))

            lookup_ids.add(int(row['issuer_id']))
            lookup_corp_ids.add(int(row['issuer_corporation_id']))

            row['region_id'] = region_id

            contract_rows.append(row)

        # Fetch bulk data
        char_map = Character.objects.in_bulk(lookup_ids)
        corp_map = Corporation.objects.in_bulk(lookup_ids | lookup_corp_ids)
        alliance_map = Alliance.objects.in_bulk(lookup_ids)
        station_map = Station.objects.in_bulk(station_ids)

        # Add missing IDs as *UNKNOWN* Characters for now
        new = []
        for new_id in lookup_ids.difference(char_map, corp_map, alliance_map, lookup_corp_ids):
            if new_id in char_map:
                continue

            char = Character(
                id=new_id,
                name="*UNKNOWN*",
            )
            new.append(char)
            char_map[new_id] = char

        if new:
            Character.objects.bulk_create(new)

        # Add missing Corporations too
        new = []
        for new_id in lookup_corp_ids.difference(corp_map):
            if new_id in corp_map:
                continue

            corp = Corporation(
                id=new_id,
                name="*UNKNOWN*",
            )
            new.append(corp)
            corp_map[new_id] = corp

        if new:
            Corporation.objects.bulk_create(new)

        # Fetch station data
        new = []
        for new_id in station_ids.difference(station_map):
            if new_id in station_map:
                continue

            station = Station(
                    id=new_id,
                    name="[Unknown Station: %d]" % new_id,
                    short_name="[Unknown Station: %d]" % new_id,
                    is_unknown=True,
            )
            new.append(station)
            station_map[new_id] = station

        if new:
            Station.objects.bulk_create(new)

        # Fetch all existing contracts
        c_map = {}
        for contract in c_filter.filter(contract_id__in=contract_ids, region_id=region_id):
            c_map[contract.contract_id] = contract

        # Finally, after all of that other bullshit, we can actually deal with
        # our goddamn contract rows
        new_contracts = []
        new_events = []

        seen_contract_ids = set()

        for row in contract_rows:
            contract_id = int(row['contract_id'])

            issuer_char = char_map.get(int(row['issuer_id']))
            if issuer_char is None:
                self.log_warn('Invalid issuer_id %s', row['issuer_id'])
                continue

            issuer_corp = corp_map.get(int(row['issuer_corporation_id']))
            if issuer_corp is None:
                self.log_warn('Invalid issuer_corporation_id %s', row['issuer_corporation_id'])
                continue

            start_station = station_map.get(int(row['start_location_id']))
            if start_station is None:
                self.log_warn('Invalid start_location_id %s', row['start_location_id'])
                continue

            end_station = station_map.get(int(row['end_location_id']))
            if end_station is None:
                self.log_warn('Invalid end_location_id %s', row['end_location_id'])
                continue

            dateIssued = self.parse_api_date(row['date_issued'], True)
            dateExpired = self.parse_api_date(row['date_expired'], True)

            type = row['type']

            '''
                Contract Types:
                  "unknown",
                  "item_exchange",
                  "auction",
                  "courier",
                  "loan"
                Contract Statuses:
                  "outstanding",
                  "in_progress",
                  "finished_issuer",
                  "finished_contractor",
                  "finished",
                  "cancelled",
                  "rejected",
                  "failed",
                  "deleted",
                  "reversed"
                Availability:
                  "public",
                  "personal",
                  "corporation",
                  "alliance"
            '''

            seen_contract_ids.add(contract_id)
            contract = c_map.get(contract_id, None)
            # Contract exists, maybe update stuff
            if contract is not None:
                continue
            # Contract does not exist, make a new one
            else:
                contract = PublicContract(
                    contract_id=contract_id,
                    region_id=region_id,
                    issuer_char=issuer_char,
                    issuer_corp=issuer_corp,
                    start_station=station_map[int(row['start_location_id'])],
                    end_station=station_map[int(row['end_location_id'])],
                    type=type,
                    status='outstanding',
                    title=row['title'],
                    #for_corp=row['for_corporation'],
                    date_issued=dateIssued,
                    date_expired=dateExpired,
                    date_lastseen=datetime.datetime.utcnow(),
                    num_days=int(row['days_to_complete']),
                    price=Decimal(row['price']),
                    reward=Decimal(row['reward']),
                    collateral=Decimal(row['collateral'] if 'collateral' in row else 0),
                    buyout=Decimal(row['buyout'] if 'buyout' in row else 0),
                    volume=Decimal(row['volume']),
                )

                new_contracts.append(contract)


        # And save the damn things
        PublicContract.objects.bulk_create(new_contracts)
        PublicContract.objects.filter(contract_id__in=seen_contract_ids).update(date_lastseen=datetime.datetime.utcnow(), status='outstanding')
        PublicContract.objects.filter(region_id=region_id, status='outstanding').exclude(contract_id__in=seen_contract_ids).update(status='unknown')
        # Force the queryset to update
        c_filter.update()

        # # Now go fetch items for each contract

        contracts_to_populate = PublicContract.objects.filter(region_id=region_id, retrieved_items=False, status='outstanding').exclude(type='Courier').exclude(status='deleted')

        if len(contracts_to_populate) > 1000:
            print('Populating Many Contracts (%d!!)! This will take a while!!' % len(contracts_to_populate))

        ttl_count = 0

        seen_contracts = []
        seen_records = set()

        new = []

	for i in range(0, len(contracts_to_populate), 500):
            urls = [self.public_contract_item_url % c.contract_id for c in contracts_to_populate[i:i+500]]
            cids = dict((self.public_contract_item_url % c.contract_id, c.id) for c in contracts_to_populate[i:i+500])
            contract_item_data = self.fetch_batch_esi_urls(urls, None, batch_size=10)

            for url, item_data in contract_item_data.items():
                success, data = item_data
            
                if not success:
                    if 'status' in headers and headers['status'] == 404:
                        seen_contracts.append(cids[url])
                        ttl_count += 1
                else:
                    try:
                        items_response = json.loads(data)
                    except:
                        continue

                    contract_items = [] 

                    for row in items_response:
                        contract_item = PublicContractItem(
                            contract_id=cids[url],
                            record_id=row['record_id'],
                            type_id=row['type_id'],
                            quantity=int(row['quantity']),
                            included=row['is_included'],
                        )

                        if 'item_id' in row:
                            contract_item.item_id = row['item_id']

                        if 'is_blueprint_copy' in row:
                            contract_item.is_blueprint_copy = row['is_blueprint_copy']

                        if 'material_efficiency' in row:
                            contract_item.material_efficiency = row['material_efficiency']

                        if 'runs' in row:
                            contract_item.runs = row['runs']

                        if 'time_efficiency' in row:
                            contract_item.time_efficiency = row['time_efficiency']

                        if row['record_id'] in seen_records:
                            continue

                        seen_records.add(row['record_id'])

                        contract_items.append(contract_item)

                        try:
                            if contract_item.type is None:
                                print('Item not found: %d' % row['type_id'])
                        except:
                            self.log_error('Item not found: %d' % row['type_id'])

                            new_item = Item(
                                id=row['type_id'],
                                name='**UNKNOWN**',
                                item_group_id=20,  # Mineral, just
                                portion_size=1,
                                base_price=1,
                            )

                            new_item.save()
                    new = new + contract_items

                    ttl_count += 1

                    seen_contracts.append(cids[url])

                if len(seen_contracts) >= 500:
                    print('Flushing %d-%d/%d contracts to DB...' % (ttl_count-len(seen_contracts), ttl_count, len(contracts_to_populate)))
                    PublicContract.objects.filter(id__in=seen_contracts).update(retrieved_items=True)
                    # Ensure we remove duplicate records
                    PublicContractItem.objects.filter(contract_id__in=seen_contracts).delete();
                    PublicContractItem.objects.filter(record_id__in=seen_records).delete()
                    PublicContractItem.objects.bulk_create(new)
                    new = []
                    seen_contracts = []
                    seen_records = set()

        if new:
            PublicContractItem.objects.filter(contract_id__in=seen_contracts).delete();
            PublicContractItem.objects.filter(record_id__in=seen_records).delete()
            PublicContractItem.objects.bulk_create(new)
            PublicContract.objects.filter(id__in=seen_contracts).update(retrieved_items=True)

        return True
