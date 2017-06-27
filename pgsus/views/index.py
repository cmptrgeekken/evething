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

from django.db import connections

from collections import defaultdict

from thing import queries

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8
from thing.helpers import humanize

from math import ceil

import re

from pgsus.parser import parse
import evepaste

from pprint import pprint,pformat

def index(request):
    return stats(request)

    #"""Index page"""
    #tt = TimerThing('index')

    # profile = request.user.profile

    #tt.add_time('profile')

    # Render template
    #out = render_page(
    #    'pgsus/index.html',
    #    {
    #        'profile': 'hello!'
    #    },
    #    request,
    #)

    #tt.add_time('template')
    #if settings.DEBUG:
    #    tt.finished()

    #return out

def stats(request):
    fuel_purchase_stats = dictfetchall(queries.fuelblock_purchase_stats)
    fuel_purchase_ttl = dictfetchall(queries.fuelblock_purchase_ttl)
    fuel_pending_stats = dictfetchall(queries.fuelblock_pending_stats)
    fuel_job_stats = dictfetchall(queries.fuelblock_job_stats)
    courier_completed_stats = dictfetchall(queries.courier_completed_stats)
    courier_pending_stats = dictfetchall(queries.courier_pending_stats)
    buyback_completed_stats = dictfetchall(queries.buyback_completed_stats)
    buyback_pending_stats = dictfetchall(queries.buyback_pending_stats)

    out = render_page(
        'pgsus/stats.html',
        dict(
            fuel_purchase_stats=fuel_purchase_stats,
            fuel_purchase_ttl=fuel_purchase_ttl[0],
            fuel_pending_stats=fuel_pending_stats,
            fuel_job_stats=fuel_job_stats,
            courier_completed_stats=courier_completed_stats[0],
            courier_pending_stats=courier_pending_stats[0],
            buyback_completed_stats=buyback_completed_stats[0],
            buyback_pending_stats=buyback_pending_stats[0],
        ),
        request,
    )

    return out


def buyback(request):
    buyback_items = PriceWatch.objects.filter(
            active=True,
            price_group__isnull=False
        ).order_by('price_group', 'item__name').distinct()

    parse_results = None
    buyback_input = ''

    latest_price = PriceHistory.objects.order_by('-date').first()
    price_last_updated = latest_price.date

    if request.method == 'POST':
        buyback_input = request.POST.get('buyback_input')

        try:
            parse_results = parse(buyback_input)
        except evepaste.Unparsable:
            parse_results = None

    total_reward = 0
    total_volume = 0

    pprinted = ''

    buyback_qty = dict()

    if parse_results is not None:
        for kind, results in parse_results['results']:
            for entry in results:
                buyback_item = buyback_items.filter(
                    item__name__iexact=entry['name']
                ).first()

                if buyback_item is not None:
                    if buyback_qty.get(buyback_item.item_id) is None:
                        buyback_qty[buyback_item.item_id] = 0
                    buyback_qty[buyback_item.item_id] += entry['quantity']

                    total_reward += entry['quantity'] * buyback_item.item.get_history_avg(pct=.95)
                    total_volume += entry['quantity'] * buyback_item.item.volume
                else:
                    parse_results['bad_lines'].append(entry['name'])

    out = render_page(
        'pgsus/buyback.html',
        dict(
            items=buyback_items,
            buyback_qty=buyback_qty,
            buyback_input=buyback_input,
            parse_results=parse_results,
            total_reward=total_reward,
            total_volume=total_volume,
            price_last_updated=price_last_updated,
            pprinted=pprinted,
        ),
        request,
    )

    return out


def fuel(request):

    fuel_blocks = Item.objects.filter(
        name__endswith='Fuel Block',
        market_group_id__gt=0,
    )

    latest_price = PriceHistory.objects.order_by('-date').first()
    price_last_updated = latest_price.date
    delivery_system_name = ''
    main_char_name = ''

    delivery_date = datetime.datetime.utcnow() + datetime.timedelta(days=14)

    all_systems = defaultdict(list)
    for result in FreighterSystem.objects.values('system__constellation__region__name', 'system__name').distinct().order_by('system__constellation__region__name', 'system__name'):
        all_systems[result['system__constellation__region__name']].append(result['system__name'])

    qty = dict()

    ttl_reward = 0
    ttl_blocks = 0

    if request.method == 'POST':
        delivery_system_name = request.POST.get('delivery_system')

        main_char_name = request.POST.get('main_char_name')

        try:
            delivery_date = datetime.datetime.strptime(request.POST.get('delivery_date'), '%Y-%m-%d')
        except ValueError:
            delivery_date = datetime.datetime.utcnow() + datetime.timedelta(days=14)

        for block in fuel_blocks:
            block_qty = request.POST.get('qty-%s' % block.id)
            block_qty = re.sub('[^\d+]', '', block_qty)

            try:
                qty[block.id] = int(block_qty)
                ttl_reward += qty[block.id] * block.get_history_avg()
                ttl_blocks += qty[block.id]
            except ValueError:
                qty[block.id] = 0

        # TODO: Move delivery configuration to database
        if delivery_system_name != 'B-9C24':
            ttl_reward += ceil(ttl_blocks / 25000) * 5000000

    min_date = datetime.datetime.utcnow() + datetime.timedelta(days=3)
    max_date = datetime.datetime.utcnow() + datetime.timedelta(days=28)


    out = render_page(
        'pgsus/fuel.html',
        dict(
            all_systems=all_systems,
            min_date=min_date,
            max_date=max_date,
            main_char_name=main_char_name,
            delivery_date=delivery_date,
            delivery_system_name=delivery_system_name,
            fuel_blocks=fuel_blocks,
            price_last_updated=price_last_updated,
            total_reward=ttl_reward,
            qty=qty,
        ),
        request
    )

    return out


def freighter(request):
    all_price_models = FreighterPriceModel.objects.filter(is_thirdparty=0).distinct()

    all_systems = defaultdict(list)
    for result in FreighterSystem.objects.filter(price_model__is_thirdparty=0).values('system__constellation__region__name', 'system__name').distinct().order_by('system__constellation__region__name', 'system__name'):
        all_systems[result['system__constellation__region__name']].append(result['system__name'])

    start_system_name = ''
    end_system_name = ''
    shipping_m3 = ''
    shipping_collateral = ''
    shipping_info = None

    errors = []

    if request.method == 'POST':
        start_system_name = request.POST.get('start_system')
        end_system_name = request.POST.get('end_system')
        try:
            shipping_m3_input = request.POST.get('shipping_m3')
            shipping_m3_input = re.sub('[^\d]+', '', shipping_m3_input)
            shipping_m3 = int(shipping_m3_input)
        except ValueError:
            errors.append('Volume invalid')

        try:
            shipping_collateral_input = request.POST.get('shipping_collateral')
            shipping_collateral_input = re.sub('[^\d]+', '', shipping_collateral_input)
            shipping_collateral = int(shipping_collateral_input)
        except ValueError:
            errors.append('Collateral invalid')

        start_system = System.objects.filter(
            name=start_system_name
        ).first()

        end_system = System.objects.filter(
            name=end_system_name
        ).first()

        if start_system is None:
            errors.append('Please select a valid start system.')

        if end_system is None:
            errors.append('Please select a valid end system.')

        start_systems = FreighterSystem.objects.filter(
            system__name=start_system_name
        )

        end_systems = FreighterSystem.objects.filter(
            system__name=end_system_name
        )

        if len(errors) == 0:
            price_models = []
            for start in start_systems:
                for end in end_systems:
                    if start.price_model.id == end.price_model.id:
                        price_models.append(start.price_model)

            shipping_info = dict(
                rate=None,
                max_collateral_exceeded=False,
                max_m3_exceeded=False,
                max_collateral=None,
                max_m3=None,
                method=None
            )
            for price_model in price_models:
                rate, method = price_model.calc(start_system, end_system, shipping_collateral, shipping_m3)
                if rate > 0 and (shipping_info['rate'] is None or shipping_info['rate'] > rate):
                    shipping_info['max_m3_exceeded'] = price_model.max_m3 < shipping_m3
                    shipping_info['max_collateral_exceeded'] = price_model.max_collateral < shipping_collateral
                    shipping_info['max_collateral'] = price_model.max_collateral
                    shipping_info['max_m3'] = price_model.max_m3
                    shipping_info['rate'] = rate
                    shipping_info['method'] = '<b>%s</b> (%s)' % (price_model.name, method)

            if shipping_info['rate'] is None:
                errors.append('Cannot ship between the selected systems.')

            if shipping_info['max_m3_exceeded']:
                errors.append('Max Volume for this route: %s m3' % humanize(shipping_info['max_m3']))
            if shipping_info['max_collateral_exceeded']:
                errors.append('Max Collateral for this route: %s ISK' % humanize(shipping_info['max_collateral']))

    out = render_page(
        'pgsus/freighter.html',
        dict(
            all_systems=all_systems,
            system_names=FreighterSystem.objects.values_list('system__name', flat=True).distinct(),
            shipping_info=shipping_info,
            price_models=all_price_models,
            start_system_name=start_system_name,
            end_system_name=end_system_name,
            shipping_m3=shipping_m3,
            shipping_collateral=shipping_collateral,
            errors=errors
        ),
        request,
    )

    return out


def pricer(request):
    parse_results = None
    text_input = ''

    if request.method == 'POST':
        text_input = request.POST.get('text_input')

        try:
            parse_results = parse(text_input)
        except evepaste.Unparsable:
            parse_results = None

    total_volume = 0

    item_list = []
    pricer_items = {}
    price_last_updated = None
    total_best = 0
    total_worst = 0
    total_shipping = 0
    total_price = 0
    if parse_results is not None:
        for kind, results in parse_results['results']:
            for entry in results:
                name = entry['name'].lower()
                if name not in pricer_items:
                    pricer_items[name] = {
                        'qty': 0,
                        'item': None,
                    }
                pricer_items[name]['qty'] += entry['quantity']

            items = Item.objects.filter(name__iregex=r'(^' + '$|^'.join([re.escape(n) for n in pricer_items.keys()]) + '$)')
            for item in items:
                pricer_item = pricer_items[item.name.lower()]
                item.get_current_orders(pricer_item['qty'])

                total_volume += item.z_ttl_volume
                total_shipping += item.z_ttl_shipping
                total_price += item.z_ttl_price_plus_shipping

                total_best += item.z_ttl_price_best
                total_worst += item.z_ttl_price_multibuy

                price_last_updated = item.z_last_updated if price_last_updated is None else max(price_last_updated, item.z_last_updated)

                item_list.append(item)

    out = render_page(
        'pgsus/pricer.html',
        dict(
            items=item_list,
            text_input=text_input,
            parse_results=parse_results,
            total_best=total_best,
            total_worst=total_worst,
            total_volume=total_volume,
            total_shipping=total_shipping,
            total_price=total_price,
            price_last_updated=price_last_updated
        ),
        request,
    )

    return out

def couriers(request):
    out = render_page(
        'pgsus/couriers.html',
        dict(

        ),
        request
    )

    return out


def overpriced(request):
    overpriced_items = []

    stations = dict()
    market_groups = dict()

    select_station_names = []
    select_market_groups = []
    pct_over = 120
    page = 1
    page_size = 50
    thirtyday_vol = 10

    item_list = ''
    item_names = set()

    if request.method == 'POST':
        select_station_names = request.POST.getlist('station_names')
        select_market_groups = request.POST.getlist('market_groups')
        pct_over = int(request.POST.get('pct_over'))
        thirtyday_vol = int(request.POST.get('thirtyday_vol'))
        page = int(request.POST.get('page'))
        page_size = int(request.POST.get('page_size'))

        if 'prev_page' in request.POST:
            page -= 1
        elif 'next_page' in request.POST:
            page += 1

        item_list = request.POST.get('item_list')

        try:
            parse_results = parse(item_list)
        except evepaste.Unparsable:
            parse_results = None

        if parse_results is not None:
            for kind, results in parse_results['results']:
                for entry in results:
                    if isinstance(entry, str):
                        # item_list = results['name']
                        continue
                    else:
                        name = entry['name'].lower()
                        item_names.add(name)

    idx = 0

    all_items = dictfetchall(queries.stationorder_overpriced)

    for item in all_items:
        if item['station_name'] not in stations:
            stations[item['station_name']] = False
        
        item_groups = [item['mg1'], item['mg2'], item['mg3'], item['mg4'], item['mg5'], item['mg6']]

        market_group_found = False
        for group in item_groups:
            if group is None:
                continue

            if group not in market_groups:
                market_groups[group] = False

            if len(select_market_groups) > 0:
                for select_group in select_market_groups:
                    if group == select_group:
                        market_group_found = True
                        break
            else:
                market_group_found = True

        if not market_group_found:
            continue

        station_found = False
        if len(select_station_names) > 0:
            for station_name in select_station_names:
                if item['station_name'] == station_name:
                    station_found = True
                    break
        else:
            station_found = True
                    
        if not station_found:
            continue

        if int(item['overpriced_pct']) < int(pct_over):
            continue

        if item['thirtyday_vol'] is None or int(item['thirtyday_vol']) < thirtyday_vol:
            continue

        if len(item_names) > 0 and item['item_name'].lower() not in item_names:
            continue

        idx += 1

        if (page-1)*page_size+1 <= idx < page*page_size:
            overpriced_items.append(item)

    for name in select_station_names:
        stations[name] = True

    for name in select_market_groups:
        market_groups[name] = True

    out = render_page(
        'pgsus/overpriced.html',
        dict(
            overpriced_items=overpriced_items,
            stations=stations,
            item_list=item_list,
            market_groups=market_groups,
            pct_over=pct_over,
            page=page,
            page_size=page_size,
            total_items=idx,
            thirtyday_vol=thirtyday_vol,
            end_item=min(page_size*page, idx),
        ),
        request
    )

    return out

def get_cursor(db='default'):
    return connections[db].cursor()


def dictfetchall(query):
    "Returns all rows from a cursor as a dict"
    cursor = get_cursor()
    cursor.execute(query)
    desc = cursor.description
    results = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    return results