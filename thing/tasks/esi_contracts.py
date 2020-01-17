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

from thing.models import Alliance, Character, CharacterApiScope, Contract, ContractItem, ContractSeeding, Corporation, Event, Item, Station, APIKey, UserProfile
from django.db.models import Q

from multiprocessing import Pool, Value, Array


class EsiContracts(APITask):
    name = 'thing.esi_contracts'

    corp_contract_url = 'https://esi.evetech.net/latest/corporations/%d/contracts/?datasource=tranquility&page=%s'
    corp_contract_item_url = 'https://esi.evetech.net/latest/corporations/%d/contracts/%d/items/?datasource=tranquility'
    
    char_contract_url = 'https://esi.evetech.net/latest/characters/%d/contracts/?datasource=tranquility&page=%s'
    char_contract_item_url = 'https://esi.evetech.net/latest/characters/%d/contracts/%d/items/?datasource=tranquility'

    def run(self):
        self.init()
        
        char_contract_scopes = CharacterApiScope.objects.filter(
            scope__in=['esi-contracts.read_character_contracts.v1']
        )

        for scope in char_contract_scopes:
            char = scope.character
            success = self.import_contracts(char, False)

        contract_scopes = CharacterApiScope.objects.filter(
            scope__in=['esi-contracts.read_corporation_contracts.v1']
        )

        seen_corps = set()

        for scope in contract_scopes:
            char = scope.character

            if 'corporation' in scope.scope:
                if 'Contract_Manager' in char.get_apiroles():
                    if char.corporation_id not in seen_corps\
                            and char.corporation_id is not None:
                        try:
                            success = self.import_contracts(char, True)
                        except:
                            success = False

                        if success:
                            seen_corps.add(char.corporation_id)

        self.update_seeding()

    def update_seeding(self):
        seed_items = ContractSeeding.objects.filter(is_active=True)

        for item in seed_items:
            item.current_qty = item.get_stock_count()
            item.corp_qty = item.get_corp_stock()
            item.alliance_qty = item.get_alliance_stock()
            item.qty_last_modified = datetime.datetime.now()
            item.estd_price = item.get_estd_price()
            item.save()


    def import_contracts(self, character, for_corp):
        char_id = character.id
        corp_id = character.corporation_id

        if corp_id is None and for_corp:
            return False

        now = datetime.datetime.now()

        if for_corp:
            c_filter = Contract.objects.filter(Q(issuer_corp_id=corp_id) | Q(assignee_id=corp_id) | Q(acceptor_id=corp_id) | Q(assignee_id=character.corporation.alliance_id))
        else:
            c_filter = Contract.objects.filter(Q(issuer_char_id=char_id) | Q(assignee_id=char_id) | Q(acceptor_id=char_id))

        contracts = []

        page = 1

        ttl_pages = None

        if for_corp:
            import_url = self.corp_contract_url
        else:
            import_url = self.char_contract_url

        success, data, headers = self.fetch_esi_url(import_url % (corp_id if for_corp else char_id, page), character, headers_to_return=['x-pages'])

        if not success:
            print('Import failed for %s: %s' % (character.name, data))
            return False

        if 'x-pages' in headers:
            ttl_pages = int(headers['x-pages'])
        else:
            ttl_pages = 1

        if ttl_pages > 1:
            urls = [import_url % (corp_id if for_corp else char_id, i) for i in range(2, ttl_pages+1)]
            all_contract_data = self.fetch_batch_esi_urls(urls, character, batch_size=20)
        else:
            all_contract_data = dict()

        all_contract_data[''] = (success, data)
        
        for url, contract_data in all_contract_data.items():
            success, data = contract_data

            if not success:
                # Failed to retrieve contract information, back out
                print('Import failed: %s' % data)
                return False

            r_contracts = json.loads(data)
            if 'response' in contracts:
                r_contracts = contracts['response']

            if len(r_contracts) == 0:
                break

            contracts.extend(r_contracts)


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

            if row['assignee_id'] != '0':
                lookup_ids.add(int(row['assignee_id']))
            if row['acceptor_id'] != '0':
                lookup_ids.add(int(row['acceptor_id']))

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
        for contract in c_filter.filter(contract_id__in=contract_ids):
            c_map[contract.contract_id] = contract

        # Finally, after all of that other bullshit, we can actually deal with
        # our goddamn contract rows
        new_contracts = []
        new_events = []

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

            assignee_id = int(row['assignee_id'])
            acceptor_id = int(row['acceptor_id'])

            dateIssued = self.parse_api_date(row['date_issued'], True)
            dateExpired = self.parse_api_date(row['date_expired'], True)

            if 'date_accepted' in row:
                dateAccepted = self.parse_api_date(row['date_accepted'], True)
            else:
                dateAccepted = None

            if 'date_completed' in row:
                dateCompleted = self.parse_api_date(row['date_completed'], True)
            else:
                dateCompleted = None

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

            contract = c_map.get(contract_id, None)
            # Contract exists, maybe update stuff
            if contract is not None:
                if contract.status != row['status']:
                    text = "Contract %s changed status from '%s' to '%s'" % (
                        contract, contract.status, row['status'])

                    new_events.append(Event(
                        user_id=1,
                        issued=now,
                        text=text,
                    ))

                    contract.status = row['status']
                    contract.date_accepted = dateAccepted
                    contract.date_completed = dateCompleted
                    contract.acceptor_id = acceptor_id
                    contract.save()

            # Contract does not exist, make a new one
            else:
                contract = Contract(
                    contract_id=contract_id,
                    issuer_char=issuer_char,
                    issuer_corp=issuer_corp,
                    assignee_id=assignee_id,
                    acceptor_id=acceptor_id,
                    start_station=station_map[int(row['start_location_id'])],
                    end_station=station_map[int(row['end_location_id'])],
                    type=type,
                    status=row['status'],
                    title=row['title'],
                    for_corp=row['for_corporation'],
                    public=(row['availability'].lower() == 'public'),
                    date_issued=dateIssued,
                    date_expired=dateExpired,
                    date_accepted=dateAccepted,
                    date_completed=dateCompleted,
                    num_days=int(row['days_to_complete']),
                    price=Decimal(row['price']),
                    reward=Decimal(row['reward']),
                    collateral=Decimal(row['collateral'] if 'collateral' in row else 0),
                    buyout=Decimal(row['buyout'] if 'buyout' in row else 0),
                    volume=Decimal(row['volume']),
                    availability=row['availability']
                )

                new_contracts.append(contract)

                # If this contract is a new contract in a non-completed state, log an event
                if contract.status in ('outstanding', 'in_progress'):
                    # if assignee_id in user_chars or assignee_id in user_corps:
                    assignee = char_map.get(assignee_id, corp_map.get(assignee_id, alliance_map.get(assignee_id)))
                    if assignee is not None:
                        text = "Contract %s was created from '%s' to '%s' with status '%s'" % (
                            contract, contract.get_issuer_name(), assignee.name, contract.status)

                        new_events.append(Event(
                            user_id=1,
                            issued=now,
                            text=text,
                        ))

        # And save the damn things
        try:
            Contract.objects.bulk_create(new_contracts)
        except:
            import sys
            print("Unexpected error:", sys.exc_info()[0])
            print(character.name)
            return False
        Event.objects.bulk_create(new_events)

        # Force the queryset to update
        c_filter.update()

        # # Now go fetch items for each contract

        contracts_to_populate = c_filter.filter(retrieved_items=False).exclude(type='Courier').exclude(status='deleted')

        if len(contracts_to_populate) > 100:
            print('Populating Many Contracts (%d!!)! This will take a while!!' % len(contracts_to_populate))

        ttl_count = 0

        seen_contracts = []
        seen_records = set()

        new = []

        item_url = self.corp_contract_item_url if for_corp else self.char_contract_item_url

        for i in range(0, len(contracts_to_populate), 100):
            urls = [item_url % (corp_id if for_corp else char_id, c.contract_id) for c in contracts_to_populate[i:i+100]]
            cids = dict((item_url % (corp_id if for_corp else char_id, c.contract_id), c.id) for c in contracts_to_populate[i:i+100])

            contract_item_data = self.fetch_batch_esi_urls(urls, character, headers_to_return=['status'], batch_size=1)

            for url, item_data in contract_item_data.items():
                success, data, headers = item_data

                cid = cids[url]

                if not success:
                    if 'status' in headers and headers['status'] == 404:
                        seen_contracts.append(cid)
                        ttl_count += 1
                else:
                    try:
                        items_response = json.loads(data)
                    except:
                        continue

                    contract_items = [] 

                    for row in items_response:
                        contract_item = ContractItem(
                            contract_id=cid,
                            record_id=row['record_id'],
                            item_id=row['type_id'],
                            quantity=int(row['quantity']),
                            raw_quantity=row.get('raw_quantity', 0),
                            singleton=row['is_singleton'],
                            included=row['is_included'],
                        )

                        if row['record_id'] in seen_records:
                            continue

                        seen_records.add(row['record_id'])

                        contract_items.append(contract_item)

                        try:
                            if contract_item.item is None:
                                print('Item not found: %d', row['type_id'])
                        except:
                            self.log_error('Item not found: %d', row['type_id'])

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

                    seen_contracts.append(cid)

            if len(seen_contracts) >= 100:
                print('Flushing %d-%d/%d contracts to DB...' % (ttl_count-len(seen_contracts), ttl_count, len(contracts_to_populate)))
                c_filter.filter(id__in=seen_contracts).update(retrieved_items=True)
                # Ensure we remove duplicate records
                ContractItem.objects.filter(contract_id__in=seen_contracts).delete();
                ContractItem.objects.filter(record_id__in=seen_records).delete()
                ContractItem.objects.bulk_create(new)
                new = []
                seen_contracts = []
                seen_records = set()

        if new:
            ContractItem.objects.filter(contract_id__in=seen_contracts).delete();
            ContractItem.objects.filter(record_id__in=seen_records).delete()
            ContractItem.objects.bulk_create(new)
            c_filter.filter(id__in=seen_contracts).update(retrieved_items=True)

        return True
