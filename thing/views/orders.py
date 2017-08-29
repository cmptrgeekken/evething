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

from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.db import connection

from thing import queries
from thing.models import *  # NOPEP8
from thing.stuff import *   # NOPEP8

from decimal import Decimal


ORDER_SLOT_SKILLS = {
    3443: 4,    # Trade
    3444: 8,    # Retail
    16596: 16,  # Wholesale
    18580: 32,  # Tycoon
}


@login_required
def orders(request):
    """Market orders"""
    # Retrieve order aggregate data
    cursor = connection.cursor()
    cursor.execute(queries.order_aggregation, (request.user.id,))
    char_orders = OrderedDict()
    for row in dictfetchall(cursor):
        row['slots'] = 5
        char_orders[row['creator_character_id']] = row

    # Retrieve trade skills that we're interested in
    order_cs = CharacterSkill.objects.filter(
        character__apikeys__user=request.user,
        skill__in=ORDER_SLOT_SKILLS,
        character__apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    )
    for cs in order_cs:
        char_id = cs.character_id
        if char_id not in char_orders:
            continue

        char_orders[char_id]['slots'] += (cs.level * ORDER_SLOT_SKILLS.get(cs.skill_id, 0))

    # Calculate free slots
    for row in char_orders.values():
        row['free_slots'] = row['slots'] - row['corp_orders'] - row['personal_orders']

    total_row = {
        'free_slots': sum(row['free_slots'] for row in char_orders.values()),
        'slots': sum(row['slots'] for row in char_orders.values()),
        'personal_orders': sum(row['personal_orders'] for row in char_orders.values()),
        'corp_orders': sum(row['corp_orders'] for row in char_orders.values()),
        'sell_orders': sum(row['sell_orders'] for row in char_orders.values()),
        'total_sells': sum(row['total_sells'] for row in char_orders.values()),
        'buy_orders': sum(row['buy_orders'] for row in char_orders.values()),
        'total_buys': sum(row['total_buys'] for row in char_orders.values()),
        'total_escrow': sum(row['total_escrow'] for row in char_orders.values()),
    }

    # Retrieve all orders
    character_ids = list(Character.objects.filter(
        apikeys__user=request.user.id,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).distinct().values_list(
        'id',
        flat=True,
    ))

    corporation_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_MARKET_ORDERS_MASK)

    orders = MarketOrder.objects.filter(
        Q(character__in=character_ids, corp_wallet__isnull=True)
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )
    orders = orders.prefetch_related('item', 'station', 'character', 'corp_wallet__corporation')
    orders = orders.order_by('station__name', '-buy_order', 'item__name')

    show_outbid = 'outbid' in request.GET and request.GET['outbid'] == '1'
    order_type = 'order_type' in request.GET and request.GET['order_type'] or 'all'
    bid_adjust = 'bid_adjust' in request.GET and Decimal(request.GET['bid_adjust']) or Decimal('0.01')

    selected_stations_qry = 'stations' in request.GET and request.GET.getlist('stations') or []

    selected_stations = set([int(id) for id in selected_stations_qry])

    # Fetch creator characters as they're not a FK relation
    creator_ids = set()
    utcnow = datetime.datetime.utcnow()
    for order in orders:
        creator_ids.add(order.creator_character_id)
        order.z_remaining = total_seconds(order.expires - utcnow)

    # Bulk query
    char_map = Character.objects.in_bulk(creator_ids)

    orders_to_show = []

    stations = set([o.station for o in orders])

    # Sort out possible chars
    for order in orders:
        order.z_creator_character = char_map.get(order.creator_character_id)
        undercut, undercut_price, undercut_volume = order.check_undercut()

        order.z_undercut_price = undercut_price

        order.z_undercut_volume = undercut_volume

        if show_outbid and order.z_undercut_price == 0:
            continue

        if order_type == 'buy' and not order.buy_order:
            continue
        
        if order_type == 'sell' and order.buy_order:
            continue;


        if len(selected_stations) > 0 and order.station_id not in selected_stations:
            continue

        orders_to_show.append(order)

    # Render template
    return render_page(
        'thing/orders.html',
        {
            'char_orders': char_orders,
            'show_outbid': show_outbid,
            'stations': stations,
            'order_type': order_type,
            'selected_stations': selected_stations,
            'bid_adjust': bid_adjust,
            'orders': orders_to_show,
            'total_row': total_row,
        },
        request,
    )

# ---------------------------------------------------------------------------
