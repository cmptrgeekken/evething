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

from thing.models import Alliance, Character, CharacterApiScope, Contract, ContractItem, Corporation, Event, Item, Station, APIKey, UserProfile


class EsiContracts(APITask):
    name = 'thing.esi_contracts'

    corp_contract_url = 'https://esi.tech.ccp.is/latest/corporations/%d/contracts/?datasource=tranquility&page=%s'
    corp_contract_item_url = 'https://esi.tech.ccp.is/latest/corporations/%d/contracts/%d/items/?datasource=tranquility'

    def run(self, base_url):
        self.init()

        contract_scopes = CharacterApiScope.objects.filter(scope='esi-contracts.read_corporation_contracts.v1')

        seen_corps = set()

        for scope in contract_scopes:
            char = scope.character

            if 'Contract_Manager' in char.get_apiroles():
                if char.corporation_id not in seen_corps:
                    self.import_contracts(char)

                    seen_corps.add(char.corporation_id)

    def import_contracts(self, character):
        corp_id = character.corporation_id
        access_token, expires = self.get_access_token(character.sso_refresh_token)

        now = datetime.datetime.now()

        c_filter = Contract.objects.filter(corporation=corp_id)

        contracts = []

        page = 1

        while True:
            data = self.fetch_esi_url(self.corp_contract_url % (corp_id, page), access_token)

            if data is False:
                break

            try:
                r_contracts = json.loads(data)
                if 'response' in contracts:
                    r_contracts = contracts['response']

                if len(r_contracts) == 0:
                    break

                contracts.extend(r_contracts)
            except:
                self.log_error('Cannot parse data: %s' % data)
                print('Cannot parse data: %s' % data)
                return

            page += 1

        # Retrieve a list of this user's characters and corporations
        # user_chars = list(Character.objects.filter(apikeys__user=self.apikey.user).values_list('id', flat=True))
        # user_corps = list(APIKey.objects.filter(user=self.apikey.user).exclude(
        #   corpasdasd_character=None).values_list('corpasd_character__corporation__id', flat=True))

        # First we need to get all of the acceptor and assignee IDs
        contract_ids = set()
        station_ids = set()
        lookup_ids = set()
        lookup_corp_ids = set()
        contract_rows = []
        # <row contract_id="58108507" issuer_id="2004011913" issuerCorp_id="751993277" assignee_id="401273477"
        #      acceptor_id="0" startStation_id="60014917" endStation_id="60003760" type="Courier" status="Outstanding"
        #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29"
        #      dateExpired="2012-08-09 06:50:29" dateAccepted="" numDays="7" dateCompleted="" price="0.00"
        #      reward="3000000.00" collateral="0.00" buyout="0.00" volume="10000"/>
        for row in contracts:
            # corp keys don't care about non-corp orders
            #if row['forCorp'] == '0':
            #    continue

            # corp keys don't care about orders they didn't issue - another fun
            # bug where corp keys see alliance contracts they didn't make  :ccp:
            if corp_id not in (
                    int(row['issuer_corporation_id']), int(row['assignee_id']), int(row['acceptor_id'])
            ):
                continue

            contract_ids.add(int(row['contract_id']))

            station_ids.add(int(row['start_location_id']))
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

        # <row contract_id="58108507" issuer_id="2004011913" issuerCorp_id="751993277" assignee_id="401273477"
        #      acceptor_id="0" startStation_id="60014917" endStation_id="60003760" type="Courier" status="Outstanding"
        #      title="" forCorp="0" availability="Private" dateIssued="2012-08-02 06:50:29" dateExpired="2012-08-09 06:50:29"
        #      dateAccepted="" numDays="7" dateCompleted="" price="0.00" reward="3000000.00" collateral="0.00" buyout="0.00"
        #      volume="10000"/>
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
            if type == 'ItemExchange':
                type = 'Item Exchange'

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
                    character=character,
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
                )
                contract.corporation_id = corp_id

                new_contracts.append(contract)

                # If this contract is a new contract in a non-completed state, log an event
                if contract.status in ('Outstanding', 'InProgress'):
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
        Contract.objects.bulk_create(new_contracts)
        Event.objects.bulk_create(new_events)

        # Force the queryset to update
        c_filter.update()

        # # Now go fetch items for each contract

        new = []
        seen_contracts = []
        contracts_to_populate = c_filter.filter(retrieved_items=False).exclude(type='Courier')
        
        ttl_count = 0
        # Apparently courier contracts don't have ContractItems support? :ccp:
        for contract in contracts_to_populate:
            if expires <= datetime.datetime.now():
                access_token, expires = self.get_access_token(character.sso_refresh_token)

            items_url = self.corp_contract_item_url % (corp_id, contract.contract_id)
            data = self.fetch_esi_url(items_url, access_token)
            if data is False:
                # self.log_error('API returned an error for url %s' % url)
                continue

            try:
                items_response = json.loads(data)
            except:
                continue

            if 'error' in items_response:
                if items_response['error'] == 'Contract not found!':
                    seen_contracts.append(contract.contract_id)
                    ttl_count += 1
                    if len(seen_contracts) % 10 == 0:
                        time.sleep(10)
                    continue
                elif items_response['error'] == 'expired':
                    access_token, expires = self.get_access_token(character.sso_refresh_token)

            contract_items = dict()

            for row in items_response:
                contract_item = ContractItem(
                    contract_id=contract.contract_id,
                    item_id=row['type_id'],
                    quantity=int(row['quantity']),
                    raw_quantity=row.get('raw_quantity', 0),
                    singleton=row['is_singleton'],
                    included=row['is_included'],
                )

                try:
                    if contract_item.item.id not in contract_items:
                        contract_items[contract_item.item.id] = contract_item
                    else:
                        contract_items[contract_item.item.id].quantity += int(contract_item.quantity)
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

                    if contract_item.item.id not in contract_items:
                        contract_items[contract_item.item.id] = contract_item
                    else:
                        contract_items[contract_item.item.id].quantity += int(contract_item.quantity)

            ttl_count += 1
            new = new + contract_items.values()

            seen_contracts.append(contract.contract_id)

            if len(seen_contracts) >= 10:
                ContractItem.objects.bulk_create(new)
                c_filter.filter(contract_id__in=seen_contracts).update(retrieved_items=True)
                new = []
                seen_contracts = []
                time.sleep(10)
        if new:
            ContractItem.objects.bulk_create(new)
            c_filter.filter(contract_id__in=seen_contracts).update(retrieved_items=True)

        return True
