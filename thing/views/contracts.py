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

from django.contrib.auth.decorators import login_required
from django.db import connections
from django.db.models import F

from math import ceil

from collections import defaultdict

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8
from thing.helpers import commas
from thing import queries

from pprint import pformat


def get_ids(request):
    """Contracts"""
    character_ids = list(Character.objects.filter(
        apikeys__user=request.user.id,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).distinct().values_list(
        'id',
        flat=True,
    ))

    corporation_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_CONTRACTS_MASK)

    return character_ids, corporation_ids

@login_required
def contracts(request):
    """Contracts"""
    character_ids, corporation_ids = get_ids(request)

    # Whee~
    contracts = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station')
    contracts = contracts.filter(
        Q(character__in=character_ids, corporation__isnull=True)
        |
        Q(corporation__in=corporation_ids)
    )

    contract_list, char_map, corp_map, alliance_map = populate_contracts(contracts)

    # Render template
    return render_page(
        'thing/contracts.html',
        dict(
            characters=character_ids,
            contracts=contract_list,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        request,
        character_ids,
        corporation_ids,
    )


@login_required
def item_contracts(request):
    character_ids, corporation_ids = get_ids(request)

    cursor = get_cursor()
    cursor.execute(queries.buyback_contracts + ' UNION ' + queries.fuelblock_purchase_contracts)

    contract_ids = [col[0] for col in cursor.fetchall()]

    contracts_to_display = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station').filter(
        contract_id__in=contract_ids,
    ).exclude(
        status__in=['Completed', 'Deleted', 'Rejected', 'finished'],
    ).exclude(
        issuer_char_id=F('corporation_id'),
    )

    contract_list, char_map, corp_map, alliance_map = populate_contracts(contracts_to_display)

    for contract in contract_list:
        contract.z_reward_high = False
        contract.z_reward_low = False
        contract.z_reward_diff = 0
        contract.z_reward = max(contract.reward, contract.price)
        contract.z_calculated_reward = 0
        contract.z_items = ''

        contract_items = ContractItem.objects.select_related('item').filter(
            contract_id=contract.contract_id
        )

        buyback_items_query = PriceWatch.objects.filter(
            active=True,
            price_group__isnull=False
        ).distinct()

        buyback_items = dict()

        for b_item in buyback_items_query:
            buyback_items[b_item.item_id] = b_item

        for contract_item in contract_items:
            if contract_item.item_id not in buyback_items:
                contract.z_invalid_item = True
                continue

            buyback_item = buyback_items[contract_item.item_id]

            if not contract_item.included:
                buyback_price = buyback_item.get_price(issued=contract.date_issued, pct=1)
            else:
                buyback_price = buyback_item.get_price(issued=contract.date_issued)

            contract.z_calculated_reward += contract_item.quantity * buyback_price
            contract.z_items += '<div>%s %s</div>' % (commas(contract_item.quantity), contract_item.item.name)

            if contract_item.item.name.endswith("Fuel Block") and not contract_item.included:
                if contract.start_station is not None and contract.start_station.system is not None and contract.start_station.system.name != 'B-9C24':
                    contract.z_calculated_reward += ceil(float(contract_item.quantity) / 25000) * 5000000

        # Allow for 2% wiggle room
        if float(contract.z_calculated_reward) < float(contract.z_reward)*.98:
            contract.z_reward_high = True
        elif float(contract.z_calculated_reward) > float(contract.z_reward) * 1.02:
            contract.z_reward_low = True

        contract.z_diff = float(contract.z_reward) - contract.z_calculated_reward
        if contract.z_calculated_reward > 0:
            contract.z_diff_pct = round(contract.z_diff / contract.z_calculated_reward, 4)*100
        else:
            contract.z_diff_pct = 'N/A'

    # Render template
    return render_page(
        'thing/item_contracts.html',
        dict(
            characters=character_ids,
            contracts=contract_list,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        request,
        character_ids,
        corporation_ids,
    )


@login_required
def courier_contracts(request):
    character_ids, corporation_ids = get_ids(request)

    cursor = get_cursor()
    cursor.execute(queries.courier_contracts)

    contract_ids = [col[0] for col in cursor.fetchall()]

    contracts_to_display = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station').filter(
        contract_id__in=contract_ids,
    ).exclude(status__in=['Rejected', 'Failed', 'Completed', 'Deleted', 'finished'])

    contract_list, char_map, corp_map, alliance_map = populate_contracts(contracts_to_display)

    freighter_map = defaultdict(list)
    for fpm in FreighterPriceModel.objects.filter(is_thirdparty=False).select_related():
        for region, systems in fpm.supported_systems().items():
            for system in systems:
                freighter_map[system].append(fpm)

    for contract in contract_list:
        contract.z_price_model = None
        contract.z_shipping_rate = None
        contract.z_shipping_method = None
        contract.z_collateral_invalid = False
        contract.z_m3_invalid = False
        contract.z_shipping_invalid = False
        contract.z_reward_high = False
        contract.z_reward_low = False
        contract.z_reward_diff = 0
        contract.z_has_station = False

        start_system_name = contract.start_station.system.name if contract.start_station.system else '[Unknown]'
        end_system_name = contract.end_station.system.name if contract.end_station.system else '[Unknown]'

        if start_system_name in freighter_map and end_system_name in freighter_map:
            start_systems = freighter_map[start_system_name]
            end_systems = freighter_map[end_system_name]
        else:
            contract.z_shipping_invalid = True
            continue

        price_models = []
        if start_systems is not None and end_systems is not None:
            for start in start_systems:
                for end in end_systems:
                    if start.id == end.id:
                        price_models.append(start)

            for price_model in price_models:
                rate, method, ly = price_model.calc(contract.start_station.system, contract.end_station.system,
                                                contract.collateral, contract.volume)
                if rate > 0 and (contract.z_shipping_rate is None or contract.z_shipping_rate > rate)\
                        and (price_model.max_m3 > contract.volume):
                    contract.z_shipping_rate = rate
                    contract.z_shipping_method = method
                    contract.z_price_model = price_model

        if contract.z_price_model is None:
            contract.z_shipping_invalid = True
        else:
            if contract.z_price_model.max_m3 < contract.volume:
                contract.z_volume_invalid = True
            if contract.z_price_model.max_collateral < contract.collateral:
                contract.z_collateral_invalid = True

            if not contract.start_station.is_citadel or not contract.end_station.is_citadel:
                contract.z_shipping_rate += 5000000

            contract.z_reward_diff = contract.z_shipping_rate - contract.reward
            if contract.reward == 0:
                contract.z_reward_low = True
            elif float(contract.z_reward_diff) / float(contract.reward) > 0.05:
                contract.z_reward_low = True
            elif float(contract.z_reward_diff) / float(contract.reward) < -0.05:
                contract.z_reward_high = True

        if not contract.start_station.is_citadel or not contract.end_station.is_citadel:
            contract.z_has_station = True

    # Render template
    return render_page(
        'thing/courier_contracts.html',
        dict(
            characters=character_ids,
            contracts=contract_list,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        request,
        character_ids,
        corporation_ids,
    )


@login_required
def contract_items(request):
    """Contracts"""
    character_ids = list(Character.objects.filter(
        apikeys__user=request.user.id,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).distinct().values_list(
        'id',
        flat=True,
    ))

    corporation_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_CONTRACTS_MASK)

    # Whee~
    contracts = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station', 'contract_items')
    contracts = contracts.filter(
        Q(character__in=character_ids, corporation__isnull=True)
        |
        Q(corporation__in=corporation_ids)
    )

    contract_id = request.GET.get('id')

    contracts = contracts.filter(
        Q(id=int(contract_id))
    )



    return render_page(
        'thing/contract_items.html',
        dict(
            contracts=contracts,
        ),
        request
    )


def populate_contracts(contracts):
    lookup_ids = set()
    for contract in contracts:
        # Add the ids to the lookup set
        if contract.assignee_id:
            lookup_ids.add(contract.assignee_id)
        if contract.acceptor_id:
            lookup_ids.add(contract.acceptor_id)

    # Do some lookups
    char_map = Character.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)

    # Now attach those to each contract
    contract_ids = set()
    contract_list = []
    for contract in contracts:
        # Skip duplicate contracts
        if contract.contract_id in contract_ids:
            continue
        contract_ids.add(contract.contract_id)
        contract_list.append(contract)

        # Assign a status icon to each contract
        if contract.status.startswith('Completed'):
            contract.z_status_icon = 'completed'
        elif contract.status == 'InProgress':
            contract.z_status_icon = 'inprogress'
        elif contract.status in ('Cancelled', 'Deleted', 'Failed', 'Rejected'):
            contract.z_status_icon = 'failed'
        elif contract.status == 'Outstanding':
            contract.z_status_icon = 'outstanding'
        else:
            contract.z_status_icon = 'unknown'

        if contract.assignee_id:
            # Assignee
            char = char_map.get(contract.assignee_id, None)
            if char is not None:
                contract.z_assignee_char = char

            corp = corp_map.get(contract.assignee_id, None)
            if corp is not None:
                contract.z_assignee_corp = corp

            alliance = alliance_map.get(contract.assignee_id, None)
            if alliance is not None:
                contract.z_assignee_alliance = alliance

            # Acceptor
            char = char_map.get(contract.acceptor_id, None)
            if char is not None:
                contract.z_acceptor_char = char

            corp = corp_map.get(contract.acceptor_id, None)
            if corp is not None:
                contract.z_acceptor_corp = corp

    return contract_list, char_map, corp_map, alliance_map

def get_cursor(db='default'):
    return connections[db].cursor()
