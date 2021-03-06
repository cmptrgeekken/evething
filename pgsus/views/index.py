## ------------------------------------------------------------------------------
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

from thing.utils import dictfetchall

from thing.models import *  # NOPEP8
from thing.stuff import render_page, datetime  # NOPEP8
from thing.helpers import humanize
from thing.utils import ApiHelper

from django.db.models import Q
from django.shortcuts import redirect, render

from django.http import HttpResponse, JsonResponse, Http404

from pgsus import Calculator

from math import ceil

import re

import simplejson as json

from pgsus.parser import parse, iter_types
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

    out = render_page(
        'pgsus/stats.html',
        dict(
            login_prompt=request.GET.get('login') == '1',
            thankyou=request.GET.get('thankyou') == '1',
        ),
        request,
    )

    return out

def svg(request):
    import urllib2

    path = request.GET.get('path')
    type = request.GET.get('type')

    route = 'http://evemaps.dotlan.net/svg/'

    if type == 'universe':
        route += 'Universe.svg'
    else:
        raise Http404

    route += '?&path=%s' % path

    response = urllib2.urlopen(route)

    content = response.read()

    http_response = HttpResponse(content, content_type='image/svg+xml')
    http_response['Content-Length'] = len(content)

    return http_response

def api_jumpgates(request):
    current_jbs = dictfetchall(queries.current_bridges)

    return JsonResponse(dict(gates=current_jbs))

def api_lys(request):
    systems = request.GET.getlist('system')
    if not systems:
        systems = request.GET.getlist('systems')

    if len(systems) == 1:
        systems = re.split(',|:',systems[0])

    query = '''
    SELECT SQRT(POW(md1.x-md2.x,2)+POW(md1.y-md2.y,2)+POW(md1.z-md2.z,2))/9460730472580800 AS lys
    FROM thing_system s1
         INNER JOIN thing_system s2
         INNER JOIN thing_mapdenormalize md1 ON s1.id=md1.item_id
         INNER JOIN thing_mapdenormalize md2 ON s2.id=md2.item_id
         WHERE s1.name=%s AND s2.name=%s
    '''

    
    cursor = connections['default'].cursor()

    ttl_lys = 0

    for i in range(0,len(systems)-1):
        start = systems[i]
        end = systems[i+1]

        cursor.execute(query, [start, end])

        ttl_lys += float(cursor.fetchone()[0])

    return JsonResponse(dict(lys=round(ttl_lys,2)))


def api_systems(request):
    systems = System.objects.filter(name__istartswith=request.GET.get('term'))

    results = list()

    for s in systems:
        result = dict()
        result['text'] = s.name
        result['id'] = s.id
        result['region'] = s.constellation.region.name

        results.append(result)

    return JsonResponse(dict(items=results))

def add_waypoint(request):
    waypoint_url = 'https://esi.evetech.net/latest/ui/autopilot/waypoint/?datasource=tranquility&add_to_beginning=false&clear_other_waypoints=false&destination_id=%s'

    if 'char' in request.session:
        charid = request.session['char']['id']

        scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()

        dest = request.GET.get('waypoint')

        if scope is not None:
            helper = ApiHelper()

            helper.fetch_esi_url(waypoint_url % dest, scope.character, method='post')

    return HttpResponse('')

def api_stations(request):
    name = request.GET.get('term')

    stations = list()
    if len(name) >= 3:
        stations = Station.objects.filter(name__icontains=name)

    return JsonResponse(dict(
        items=[{'id': s.id, 'name': s.name} for s in stations]
    ))

def api_characters(request):
    name = request.GET.get('term')

    chars = list()
    if len(name) >= 3:
        chars = Character.objects.filter(name__istartswith=name)

    return JsonResponse(dict(
        items=[{'id': c.id, 'name': c.name} for c in chars]
    ))

def api_populatestations(request):
    search_url = 'https://esi.evetech.net/latest/characters/%s/search/?datasource=tranquility&categories=structure&search=%s'
    structure_url = 'https://esi.evetech.net/latest/universe/structures/%s?datasource=tranquility'
    system = request.GET.get('system')

    helper = ApiHelper()
    kgb = Character.objects.filter(name='KenGeorge Beck').first()

    success, response = helper.fetch_esi_url(search_url % (kgb.id, system), kgb)

    if not success:
        return JsonResponse(dict(
            success=False
        ))

    station_ids = json.loads(response)

    results = list()

    all_success = True

    if len(station_ids) > 0:
        for station_id in station_ids['structure']:
            success, response = helper.fetch_esi_url(structure_url % station_id, kgb)

            if not success:
                results.append(response)
                continue

            esi_station = json.loads(response)

            station = Station.objects.filter(id=station_id).first()

            if station is None:
                station = Station()
                results.append(esi_station['name'])
            elif station.is_unknown:
                results.append(esi_station['name'])

            station.id = station_id
            station.name = esi_station['name']
            station.corporation_id = esi_station['owner_id']
            station.system_id = esi_station['solar_system_id']
            station.type_id = esi_station['type_id']
            station.is_citadel = True
            station.is_unknown = False
            station.deleted = False

            station.save()
    else:
        results.append('No structure found.')

    return JsonResponse(dict(
        success=all_success,
        results=results
    ))

def api_jumpgate_history(request):
    station_id = int(request.GET.get('id'))
    page = int(request.GET.get('page') or '1')
    size = int(request.GET.get('size') or '20')

    history = dictfetchall("SELECT * FROM thing_jumpgate_history WHERE station_id=%d ORDER BY last_updated DESC LIMIT %d,%d" % (station_id, (page-1)*size,size))

    return JsonResponse(dict(items=history))


def open_window(request):
    window_url = 'https://esi.evetech.net/latest/ui/openwindow/%s/?datasource=tranquility&%s=%s'

    if 'char' in request.session:
        charid = request.session['char']['id']

        scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.open_window.v1').first()

        id = request.GET.get('id')
        type = request.GET.get('type')

        if id is not None and scope is not None:
            helper = ApiHelper()

            if type == 'contract':
                url = window_url % (type, 'contract_id', id)
            elif type == 'information':
                url = window_url % (type, 'target_id', id)
            elif type == 'marketdetails':
                url = window_url % (type, 'type_id', id)
            else:
                url = None

            if url is not None:
                helper.fetch_esi_url(url, scope.character, method='post')

    return HttpResponse('')


def buyback_old(request):
    return redirect('/buyback/pennys-fuel-buyback')
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

    buyback_qty = dict()

    if parse_results is not None:
        for kind, results in parse_results['results']:
            for entry in iter_types(kind, results):
                buyback_item = buyback_items.filter(
                    item__name__iexact=entry['name']
                ).first()

                if buyback_item is not None:
                    if buyback_qty.get(buyback_item.item_id) is None:
                        buyback_qty[buyback_item.item_id] = 0
                    buyback_qty[buyback_item.item_id] += entry['quantity']

                    total_reward += entry['quantity'] * buyback_item.get_price()
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
            price_last_updated=price_last_updated
        ),
        request,
    )

    return out


def fuel(request):

    fuel_blocks = Item.objects.filter(
        name__endswith='Fuel Block',
        market_group_id__gt=0,
    ).order_by('name')

    latest_price = PriceHistory.objects.order_by('-date').first()
    price_last_updated = latest_price.date
    delivery_system_name = ''
    main_char_name = ''

    delivery_date = datetime.datetime.utcnow() + datetime.timedelta(days=14)

    all_systems = defaultdict(set)

    for fpm in FreighterPriceModel.objects.filter(is_thirdparty=0):
        pm_systems = fpm.supported_systems()

        for r in pm_systems.keys():
            all_systems[r].update(pm_systems[r])

    for region in all_systems.keys():
        all_systems[region] = sorted(all_systems[region])

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
    all_price_models = FreighterPriceModel.objects.filter(is_thirdparty=False).distinct()

    all_systems = defaultdict(set)

    for fpm in FreighterPriceModel.objects.filter(is_thirdparty=False):
        pm_systems = fpm.supported_systems()

        for r in pm_systems.keys():
            all_systems[r].update(pm_systems[r])

    for region in all_systems.keys():
        all_systems[region] = sorted(all_systems[region])

    start_system_name = ''
    end_system_name = ''
    shipping_m3 = ''
    shipping_collateral = ''
    shipping_info = None
    is_station = False

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
            Q(system_id=start_system.id)
            | Q(constellation_id=start_system.constellation_id)
            | Q(region_id=start_system.constellation.region_id)
        )

        end_systems = FreighterSystem.objects.filter(
            Q(system_id=end_system.id)
            | Q(constellation_id=end_system.constellation_id)
            | Q(region_id=end_system.constellation.region_id)
        )

        if len(errors) == 0:
            price_models = []
            for start in start_systems:
                for end in end_systems:
                    if start.price_model.id == end.price_model.id and not start.price_model.is_thirdparty:
                        price_models.append(start.price_model)

            shipping_info = dict(
                rate=None,
                max_collateral_exceeded=False,
                max_m3_exceeded=False,
                max_collateral=None,
                ttl_lys=0,
                max_m3=None,
                method=None
            )
            for price_model in price_models:
                rate, method, lys = price_model.calc(start_system, end_system, shipping_collateral, shipping_m3)
                trips = int(ceil(shipping_m3 / price_model.max_m3))

                rate *= trips

                if trips > 1:
                    continue

                if rate > 0 and (shipping_info['rate'] is None or shipping_info['rate'] > rate):
                    shipping_info['max_m3_exceeded'] = price_model.max_m3 < shipping_m3
                    shipping_info['max_collateral_exceeded'] = price_model.max_collateral < shipping_collateral
                    shipping_info['max_collateral'] = price_model.max_collateral
                    shipping_info['max_m3'] = price_model.max_m3
                    shipping_info['ttl_lys'] = lys
                    shipping_info['rate'] = rate
                    shipping_info['method'] = '<b>%s</b> (%s)' % (price_model.name, method)
                    shipping_info['trips'] = trips

            if 'trips' in shipping_info and shipping_info['trips'] > 1:
                shipping_info['rate'] /= shipping_info['trips']
                errors.append('You need at least %d contracts at the shown rate to use this method.' % shipping_info['trips'])

            if shipping_info['rate'] is None:
                errors.append('Cannot ship between the selected systems. Perhaps your m3 is too high?')

            if shipping_info['max_m3_exceeded']:
                errors.append('Max Volume for this route: %s m3' % humanize(shipping_info['max_m3']))
            if shipping_info['max_collateral_exceeded']:
                errors.append('Max Collateral for this route: %s ISK' % humanize(shipping_info['max_collateral']))

            if is_station and shipping_info['rate'] is not None:
                shipping_info['rate'] += 5000000
                errors.append('A fee of 5,000,000 ISK has been applied since pick up or destination is a station.')

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
            is_station=is_station,
            errors=errors
        ),
        request,
    )

    return out

def pricer(request, key):
    parse_results = None
    text_input = ''
    existing_ores = None

    reprocess_pct = 87.6

    input_data = None
    output_data = None

    is_post = False

    if key is not None:
        data = Links.objects.filter(page='pricer', path=key).first()

        if data is not None:
            input_data = json.loads(data.input_data)
            try:
                output_data = json.loads(data.output_data)

                is_post = True
            except:
                is_post = True
        else:
            key = None
    elif request.method == 'POST':
        input_data = dict(
            text_input=request.POST.get('text_input'),
            existing_ores=request.POST.get('existing_ores'),
            reprocess_pct=request.POST.get('reprocess_pct'),
            destination_station=request.POST.get('destination_station'),
            source_stations=request.POST.getlist('source_stations'),
            multiplier=request.POST.get('multiplier'),
            buy_all_tolerance=request.POST.get('buy_all_tolerance'),
            compress_ores='compress_ores' in request.POST
        )

        is_post = True


    if is_post:
        text_input = input_data.get('text_input')
        existing_ores = input_data.get('existing_ores') or ''

        try:
            parse_results = parse(text_input)
        except evepaste.Unparsable:
            parse_results = None

        try:
            existing_ores = parse(existing_ores)
        except evepaste.Unparsable:
            existing_ores = None

        try:
            reprocess_pct = float(input_data.get('reprocess_pct'))
        except Exception:
            ''''''


    source_stations = None
    destination_station = None

    total_volume = 0

    stations = dict()

    station_list = Station.objects.filter(load_market_orders=True)

    for station in station_list:
        stations[station.id] = station

    pricer_items = {}
    price_last_updated = None
    total_best = 0
    total_worst = 0
    total_shipping = 0
    total_price_with_shipping = 0
    multiplier = 1
    buy_all_tolerance = 2
    has_unfulfilled = False
    compress_ores = False

    compressed_minerals = None
    mineral_value_ratio = None
    total_mineral_price = None
    compress_method = None

    if is_post:
        destination_station = int(input_data.get('destination_station'))
        source_stations = [int(i) for i in input_data.get('source_stations')]
        multiplier = int(input_data.get('multiplier'))
        buy_all_tolerance = float(input_data.get('buy_all_tolerance'))
        compress_ores = input_data.get('compress_ores')

        for id in source_stations:
            stations[id].z_source_selected = True

        stations[destination_station].z_destination_selected = True
    else:
        for id in stations:
            if stations[id].name.startswith("Jita") or stations[id].name.startswith("R1O"):
                stations[id].z_source_selected = True
            if stations[id].name.startswith("R1O"):
                stations[id].z_destination_selected = True

    stations = [stations[id] for id in stations]

    stations.sort(key=lambda s: s.name)

    station_orders = dict()
    items_list = []
    bad_lines = dict()

    ore_stock = dict()

    if existing_ores is not None:
        for kind, parsed in existing_ores['results']:
            for entry in iter_types(kind, parsed):
                name = entry['name'].lower()
                if name not in ore_stock:
                    ore_stock[name] = 0
                ore_stock[name] += entry.get('quantity', 1)

    if parse_results is not None:
        for kind, parsed in parse_results['results']:
            for entry in iter_types(kind, parsed):
                name = entry['name'].lower()
                if name not in pricer_items:
                    pricer_items[name] = {
                        'qty': 0,
                        'item': None,
                    }
                pricer_items[name]['qty'] += entry.get('quantity', 1)*multiplier
                bad_lines[name] = True

        items = Item.objects.filter(name__iregex=r'(^' + '$|^'.join([re.escape(n) for n in pricer_items.keys()]) + '$)')

        items = list(items.order_by('name'))

        minerals_to_compress = dict()

        mineral_items = []

        for item in items[:]:
            item.z_orders_loaded = False

            if compress_ores:
                if item.item_group.name in ['Mineral', 'Ice Product']:
                    bad_lines[item.name.lower()] = False
                    pricer_item = pricer_items[item.name.lower()]
                    minerals_to_compress[item.id] = int(pricer_item['qty'])
                    mineral_items.append(item)
                    items.remove(item)

        if len(minerals_to_compress.values()) > 0:
            calculator = Calculator()
            results =\
                calculator.calculate_optimal_ores(minerals_to_compress,
                                                  source_station_ids=source_stations,
                                                  dest_station_id=destination_station,
                                                  allow_mineral_purchase=True,
                                                  reprocess_pct=reprocess_pct/100)
            fulfilled_all = True
            all_items = None

            if not results:
                for i in mineral_items:
                    items.append(i)
            else:
                all_items, fulfilled_all, mineral_value_ratio, compressed_minerals, total_mineral_price, compress_method = results

            if not fulfilled_all:
                for mineral in compressed_minerals:
                    if mineral.z_desired_qty > mineral.z_fulfilled_qty:
                        pricer_items[mineral.name.lower()] = dict(qty=mineral.z_desired_qty - mineral.z_fulfilled_qty)
                        items.append(mineral)

            if all_items is not None:
                for item in all_items:
                    item.z_orders_loaded = True
                    items.append(item)

        for item in items:
            bad_lines[item.name.lower()] = False

            if not item.z_orders_loaded:
                pricer_item = pricer_items[item.name.lower()]
                item.get_current_orders(pricer_item['qty'],
                                        buy=False,
                                        source_station_ids=source_stations,
                                        ignore_seed_items=False,
                                        dest_station_id=destination_station,
                                        buy_tolerance=buy_all_tolerance/100,
                                        include_variants=True,
                                        scale_by_repro=True)

            total_volume += item.z_ttl_volume
            total_shipping += item.z_ttl_shipping

            total_best += item.z_ttl_price_best
            total_worst += item.z_ttl_price_multibuy
            total_price_with_shipping += item.z_ttl_price_with_shipping

            items_list.append(item)

            if item.z_qty_remaining > 0:
                has_unfulfilled = True

            if compressed_minerals:
                for m in compressed_minerals:
                    if m.z_desired_qty > m.z_fulfilled_qty:
                        has_unfulfilled = True

            for sid in item.z_orders:
                order_list = item.z_orders[sid]
                if order_list.station_name not in station_orders:
                    station_orders[order_list.station_name] = dict(
                        orders=[],
                        total_volume=0,
                        total_price_multibuy=0,
                        total_price_best=0,
                        total_shipping=0,
                        total_price_with_shipping=0,
                        last_updated=None,
                        multibuy_all='',
                        multibuy_best='',
                    )

                entry = station_orders[order_list.station_name]
                entry['total_volume'] += order_list.total_volume
                entry['total_price_multibuy'] += order_list.total_price_multibuy
                entry['total_price_best'] += order_list.total_price_best
                entry['total_shipping'] += order_list.total_shipping
                entry['total_price_with_shipping'] += order_list.total_price_with_shipping
                entry['last_updated'] = order_list.last_updated if entry['last_updated'] is None else max(entry['last_updated'], order_list.last_updated)

                entry['multibuy_all'] += '%s x%d\n' % (order_list.item_name, order_list.total_quantity)

                if order_list.multibuy_ok:
                    entry['multibuy_best'] += '%s x%d\n' % (order_list.item_name, order_list.total_quantity)

                entry['orders'].append(order_list)

    bad_lines = [k for k, v in bad_lines.items() if v]

    output = output_data if output_data is not None else dict(
		items_list=items_list,
    		station_orders=station_orders,
		text_input=text_input,
		compress_method=compress_method,
		compress_ores=compress_ores,
		bad_lines=bad_lines,
		has_unfulfilled=has_unfulfilled,
		parse_results=parse_results,
		total_best=total_best,
		total_worst=total_worst,
		total_volume=total_volume,
		total_shipping=total_shipping,
		total_price_with_shipping=total_price_with_shipping,
		price_last_updated=price_last_updated,
		stations=stations,
		multiplier=multiplier,
		buy_all_tolerance=buy_all_tolerance,
		compressed_minerals=compressed_minerals,
		mineral_value_ratio=mineral_value_ratio,
		total_mineral_price=total_mineral_price,
		reprocess_pct=reprocess_pct
	    ) 

    if is_post and key is None:
        link = Links()
        link.page = 'pricer'
	link.path = link.genKey()
        link.input_data = json.dumps(input_data)
        #link.output_data = json.dumps(output)
	link.save()

	output['link_key'] = link.path
    else:
	output['link_key'] = key

    out = render_page(
        'pgsus/pricer.html',
	output,
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
    thirtyday_order = 5
    thirtyday_profit = 0

    item_list = ''
    item_names = set()

    if request.method == 'POST':
        select_station_names = request.POST.getlist('station_names')
        select_market_groups = request.POST.getlist('market_groups')
        pct_over = int(request.POST.get('pct_over'))
        thirtyday_vol = int(request.POST.get('thirtyday_vol'))
        thirtyday_order = int(request.POST.get('thirtyday_order'))
        thirtyday_profit = int(request.POST.get('thirtyday_profit'))
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

    all_items = dictfetchall(queries.stationorder_overpriced_cached + " ORDER BY overpriced_pct DESC")

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

        if pct_over > 0 and int(item['overpriced_pct']) < int(pct_over):
            continue

        if item['thirtyday_vol'] is None or int(item['thirtyday_vol']) < thirtyday_vol:
            continue

        if item['thirtyday_order'] is None or int(item['thirtyday_order']) < thirtyday_order:
            continue

        if item['thirtyday_vol'] * (item['twentypct_profit'] - item['jita_price_plus_shipping']) < thirtyday_profit:
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
            thirtyday_order=thirtyday_order,
            thirtyday_profit=thirtyday_profit,
            end_item=min(page_size*page, idx),
        ),
        request
    )

    return out


def seeding(request):
    seed_data = dictfetchall(queries.stationorder_seeding_qty)

    low_qty_only = True
    if not request.GET.get('low_qty_only'):
        low_qty_only = False

    selected_stations = [int(i) for i in request.GET.getlist('station')]

    seeder = request.GET.get('seeder')

    seed_items =[]
    stations = dict()
    seeders = set()
    for data in seed_data:
        stations[data['station_id']] = data['station_name']
        seeders.add(data['seeder_name'])

        if data['volume_remaining'] is None or data['volume_remaining'] < data['min_qty']:
            data['state'] = 'danger'
        elif data['volume_remaining'] < data['min_qty'] * 1.2:
            data['state'] = 'warning'

        if low_qty_only and 'state' not in data:
            continue

        if len(selected_stations) > 0 and data['station_id'] not in selected_stations:
            continue

        if len(seeder or '') > 0 and data['seeder_name'] != seeder:
            continue

        seed_items.append(data)

    out = render_page(
        'pgsus/seeding.html',
        dict(
            seed_data=seed_items,
            low_qty_only=low_qty_only,
            station=selected_stations,
            stations=stations,
            seeder=seeder,
            seeders=seeders,

        ),
        request
    )

    return out

def assets(request):
    from anytree import Node, RenderTree
    #if 'char' not in request.session:
    #    return redirect('/?login=1')

    #charid = request.session['char']['id']

    #char = Character.objects.filter(id=charid).first()
    char = Character.objects.filter(name='KenGeorge Beck').first()

    if request.GET.get('for_corp') == '1':
        query = queries.assetlist_corporation_query % char.corporation.id
    else:
        query = queries.assetlist_character_query % char.id

    results = dictfetchall(query)

    assets = dict()

    node_list = dict()

    total_value = 0
    total_m3 = 0

    root_node = Node('Universe', label='Universe', value=0, m3=0, entry=None, quantity=0)

    for result in results:
        if result['station_name'] is not None:
            key = result['station_name']
            loc_id = result['station_id']
        else:
            key = result['system_name']
            loc_id = result['system_id']

        if loc_id not in node_list:
            node_list[loc_id] = Node(loc_id, label=key, value=0, m3=0, entry=None, quantity=0, parent=root_node)

        if result['parent_name'] is None:
            container_id = '%s - %s' % (result['parent_id'], result['location_flag'])
        else:
            container_id = '%s - %s' % (loc_id, result['location_flag'])

        if container_id not in node_list:
            node_list[container_id] = Node(container_id, value=0, m3=0, label=result['location_flag'], entry=None, quantity=0)

        node_id = result['asset_id']
        node_list[node_id] = Node(node_id, parent_id=container_id, value=result['rough_value'] or 0, m3=result['m3'], label=result['item_name'], location_key=key, entry=result, quantity=result['quantity'])

    for node in node_list.values():
        if node.entry is not None:
            if node.entry['parent_id'] is None:
                node.parent = node_list[node.location_key]
            else:
                node.parent = node_list[node.container_id]
        elif node.parent is None:
            node.parent = node_list[node.container_id]

    print(RenderTree(root_node))

    return HttpResponse('Done')

    out = render_page(
        'pgsus/assets.html',
        dict(
            assets=sorted_assets,
            total_value=total_value,
            total_m3=total_m3,
        ),
        request
    )

    return out


def perms(request):
    redir = request.GET.get('redirect')
    if not redir or not redir.startswith('/'):
        redir = '/perms'

    requested_perm = request.GET.get('perm')

    char = None
    char_scopes = set()
    roles = set()

    if 'char' in request.session:
        charid = request.session['char']['id']

        char = Character.objects.filter(id=charid).first()

        char_scopes = char.get_scopes()
        roles = char.get_apiroles()

    scopes = [
        dict(scope='esi-characters.read_corporation_roles.v1', desc='Allows for reading of your roles within your corporation (e.g., Accountant, Station Manager). This is needed to determine which endpoints you have permission to access.', required=False),
        dict(scope='esi-contracts.read_character_contracts.v1', desc='Allows for reading of character contracts.', required=False),
        dict(scope='esi-contracts.read_corporation_contracts.v1', desc='Allows for reading of corporation contracts.', required=False),
        dict(scope='esi-corporations.read_structures.v1', desc='Allows for retrieval of information about corporation structures (requires Station Manager role).', required=False),
        dict(scope='esi-corporations.write_structures.v1', desc='Allows for updating vulnerability schedules for structures you have access to.', required=False),
        dict(scope='esi-universe.read_structures.v1', desc='Allows for retrieval of public structure information.', required=False),
        dict(scope='esi-search.search_structures.v1', desc='Allows for searching of structures character has access to.', required=False),
        dict(scope='esi-industry.read_corporation_mining.v1', desc='Allows for reading of moon extraction schedule (requires Station Manager role) and mining ledger (requires Accountant role).', required=False),
        dict(scope='esi-ui.open_window.v1', desc='Allows for opening of Contract, Market or Info windows in-game.', required=False),
        dict(scope='esi-location.read_location.v1', desc='Allows for reading current character location.', required=False),
        dict(scope='esi-location.read_online.v1', desc='Allows for reading if current character is online.', required=False),
        dict(scope='esi-ui.write_waypoint.v1', desc='Allows for setting and clearing of waypoints in-game.', required=False),
        dict(scope='esi-bookmarks.read_corporation_bookmarks.v1', desc='Allows for reading of corporation bookmarks.', required=False),
        dict(scope='esi-bookmarks.read_character_bookmarks.v1', desc='Allows for reading of character bookmarks.', required=False),
        dict(scope='esi-assets.read_assets.v1', desc='Allows for reading of character assets.', required=False),
        dict(scope='esi-assets.read_corporation_assets.v1', desc='Allows for reading of corporation assets (requires Director role).', required=False),
        dict(scope='esi-characters.read_notifications.v1', desc='Allows for viewing of character notifications', required=False),
        dict(scope='esi-markets.structure_markets.v1', desc='Allows for reading of structure market data', required=False),
        dict(scope='esi-wallet.read_corporation_wallets.v1', desc='Allows for reading of corporation wallets.', required=False),
    ]

    for scope in scopes:
        scope['active'] = scope['scope'] in char_scopes

    if request.method == 'POST' or requested_perm is not None or char is None:
        if requested_perm:
            requested_scopes = char_scopes
            requested_scopes.add(requested_perm)
            requested_scopes = list(char_scopes)
        else:
            requested_scopes = request.POST.getlist('scope')

        for scope in scopes:
            if scope['required']:
                requested_scopes.append(scope['scope'])

        request.session['request_scopes'] = requested_scopes

        api_helper = ApiHelper()
        oauth2_handler = api_helper.oauth_handler()

        oauth_url = oauth2_handler.authorize_url(
            ' '.join(requested_scopes),
            response_type='code',
            state='request_scopes',
        )

        if redir is not None:
            request.session['redirect'] = redir

        return redirect(oauth_url)

    return render_page(
        'pgsus/perms.html',
        dict(
            scopes=scopes,
            roles=', '.join(roles).replace('_', ' '),
        ),
        request
    )

