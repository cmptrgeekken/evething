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

from decimal import Decimal

from .apitask import APITask
import json

from thing.models import Alliance, Character, Contract, ContractItem, Corporation, Event, Station, APIKey, UserProfile


class EsiContracts(APITask):
    name = 'thing.esi_contracts'

    corp_contract_url = '/corporations/{0}/contracts/'
    corp_contract_item_url = '/corporations/{0}/contracts/{1}/items/'

    def run(self, base_url, taskstate_id, api_key, zero):
        if self.init(taskstate_id) is False:
            return

        now = datetime.datetime.now()

        character_id = 96243993
        corp_id = 99005338
        profile = UserProfile.objects.filter(id=4).first()
        access_token = self.get_access_token(profile.sso_refresh_token)

        try:
            character = Character.objects.select_related('details').get(pk=character_id)
        except Character.DoesNotExist:
            self.log_warn('Character %s does not exist!', character_id)
            return

        c_filter = Contract.objects.filter(corporation=corp_id)

        data = self.fetch_esi_url(base_url + (self.corp_contract_url % corp_id), access_token)

        if data is False:
            # self.log_error('API returned an error for url %s' % url)
            return

        try:
            contracts = json.loads(data)
        except:
            return

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

            dateIssued = self.parse_esi_date(row['date_issued'])
            dateExpired = self.parse_esi_date(row['date_expired'])

            dateAccepted = row['date_accepted']
            if dateAccepted:
                dateAccepted = self.parse_esi_date(dateAccepted)
            else:
                dateAccepted = None

            dateCompleted = row['date_completed']
            if dateCompleted:
                dateCompleted = self.parse_esi_date(dateCompleted)
            else:
                dateCompleted = None

            type = row['type']
            if type == 'ItemExchange':
                type = 'Item Exchange'

            contract = c_map.get(contract_id, None)
            # Contract exists, maybe update stuff
            if contract is not None:
                if contract.status != row['status']:
                    text = "Contract %s changed status from '%s' to '%s'" % (
                        contract, contract.status, row['status'])

                    new_events.append(Event(
                        user_id=self.apikey.user.id,
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
                    collateral=Decimal(row['collateral'] or 0),
                    buyout=Decimal(row['buyout'] or 0),
                    volume=Decimal(row['volume']),
                )
                if self.apikey.key_type == APIKey.CORPORATION_TYPE:
                    contract.corporation = self.apikey.corporation

                new_contracts.append(contract)

                # If this contract is a new contract in a non-completed state, log an event
                if contract.status in ('Outstanding', 'InProgress'):
                    # if assignee_id in user_chars or assignee_id in user_corps:
                    assignee = char_map.get(assignee_id, corp_map.get(assignee_id, alliance_map.get(assignee_id)))
                    if assignee is not None:
                        text = "Contract %s was created from '%s' to '%s' with status '%s'" % (
                            contract, contract.get_issuer_name(), assignee.name, contract.status)

                        new_events.append(Event(
                            user_id=self.apikey.user.id,
                            issued=now,
                            text=text,
                        ))

        # And save the damn things
        Contract.objects.bulk_create(new_contracts)
        Event.objects.bulk_create(new_events)

        # Force the queryset to update
        c_filter.update()

        # # Now go fetch items for each contract
        items_url = self.corp_contract_item_url % (corp_id, contract.contract_id)
        new = []
        seen_contracts = []
        # Apparently courier contracts don't have ContractItems support? :ccp:
        for contract in c_filter.filter(retrieved_items=False).exclude(type='Courier'):

            data = self.fetch_esi_url(items_url, access_token)
            if data is False:
                # self.log_error('API returned an error for url %s' % url)
                return

            try:
                items_response = json.loads(data)
            except:
                return

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

                if contract_item.item.id not in contract_items:
                    contract_items[contract_item.item.id] = contract_item
                else:
                    contract_items[contract_item.item.id].quantity += int(contract_item.quantity)

            new = new + contract_items.values()

            seen_contracts.append(contract.contract_id)

        if new:
            ContractItem.objects.bulk_create(new)
            c_filter.filter(contract_id__in=seen_contracts).update(retrieved_items=True)

        return True
