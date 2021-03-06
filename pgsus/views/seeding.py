from thing.models import *  # NOPEP8
from thing.stuff import render_page
from thing.utils import dictfetchall
from thing import queries

from django.shortcuts import redirect, render

from django.core.urlresolvers import reverse

from decimal import Decimal


from pgsus.parser import parse, iter_types
import evepaste


"""
Displays all seeding lists associated to the currently logged-in user.
"""
def seedlist(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    lists = SeedList.objects.filter(char_id=charid)

    public_lists = SeedList.objects.filter(is_private=False)

    out = render_page(
        'pgsus/seedlist.html',
        dict(
            seed_lists=lists,
            has_lists=len(lists) > 0,
            public_lists=public_lists,
        ),
        request
    )

    return out


def seededit(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    char_id = request.session['char']['id']

    parse_results = None
    seed_input = ''
    default_qty = 1
    multiplier = 1

    stations = dict()

    station_list = Station.objects.filter(load_market_orders=True)
    for station in station_list:
        station.z_seed_selected = False
        stations[station.id] = station

    list = SeedList(is_private=True)
    list_id = None

    if request.GET.get('id') is not None:
        try:
            list_id = int(request.GET.get('id'))

            list = SeedList.objects.filter(id=list_id, char_id=char_id).first()
        except Exception:
            list = None

        if list is None:
            return redirect(reverse(seedlist))

    if request.method == 'POST':
        updateMethod = request.POST.get('method')

        if updateMethod == 'update':
            list.name = request.POST.get('list_name')
            list.char_id = char_id
            list.is_private = request.POST.get('private') == 'Y'
            list.save()

            return redirect('%s?id=%d' % (reverse(seededit), list.id))

        if updateMethod == "delete":
            list.get_items().delete()
            list.delete()

            return redirect(reverse(seedlist))

        if updateMethod == "manageitems":
            del_ids = request.POST.getlist('del_id')

            ids = request.POST.getlist('seed_id')
            qties = request.POST.getlist('min_qty')

            for i in range(0, len(ids)):
                id = ids[i]
                qty = qties[i]

                seeditem = ItemStationSeed.objects.filter(id=id, list_id=list.id).first()

                if seeditem is not None:
                    seeditem.min_qty = qty
                    seeditem.save()

            if len(del_ids) > 0:
                ItemStationSeed.objects.filter(id__in=del_ids).delete()

            return redirect('%s?id=%d' % (reverse(seededit), list.id))

        if updateMethod == 'additems':
            seed_input = request.POST.get('seed_input')
            default_qty = int(request.POST.get('default_qty'))
            multiplier = int(request.POST.get('multiplier'))

            try:
                parse_results = parse(seed_input)
            except evepaste.Unparsable:
                parse_results = None

            seed_stations = [int(i) for i in request.POST.getlist('seed_stations')]

            for id in seed_stations:
                stations[id].z_seed_selected = True

            if parse_results is not None:
                for kind, results in parse_results['results']:
                    for entry in iter_types(kind, results):
                        monitor_item = Item.objects.filter(
                            name__iexact=entry['name']
                        ).first()

                        if monitor_item is not None:
                            for id in stations:
                                if stations[id].z_seed_selected:
                                    if default_qty > 0 and entry['quantity'] == 1:
                                        min_qty = default_qty
                                    else:
                                        min_qty = entry['quantity']

                                    min_qty = min_qty * multiplier

                                    existing_item = ItemStationSeed.objects.filter(
                                        list_id=list.id,
                                        item_id=monitor_item.id,
                                        station_id=id,
                                    ).first()

                                    if existing_item is not None:
                                        existing_item.min_qty += min_qty
                                        existing_item.save()
                                    else:
                                        seeditem = ItemStationSeed(
                                            list_id=list.id,
                                            item_id=monitor_item.id,
                                            min_qty=min_qty,
                                            station_id=id,
                                            active=True
                                        )

                                        seeditem.save()
                        else:
                            parse_results['bad_lines'].append(entry['name'])

                if len(parse_results['bad_lines']) == 0:
                    return redirect('%s?id=%d' % (reverse(seededit), list.id))

    stations = [stations[id] for id in stations]

    stations.sort(key=lambda s: s.name)

    seeditems = list.get_items()

    out = render_page(
        'pgsus/seededit.html',
        dict(
            seed_input=seed_input,
            stations=stations,
            list=list,
            seeditems=seeditems,
            default_qty=default_qty,
            parse_results=parse_results,
            multiplier=multiplier,
        ),
        request
    )

    return out


def seedview(request):
    if 'char' in request.session:
        char_id = request.session['char']['id']
    else:
        char_id = None

    list_id = request.GET.get('id')

    list = SeedList.objects.filter(id=list_id).first()

    if list is None or (list.is_private and list.char_id != char_id):
        return redirect('/?login=1')

    seed_data = dictfetchall(queries.stationorder_seeding_breakdown % list_id)

    low_qty_only = True
    if not request.GET.get('low_qty_only'):
        low_qty_only = False

    selected_stations = [int(i) for i in request.GET.getlist('station')]

    seed_items =[]
    stations = dict()
    for data in seed_data:
        stations[data['station_id']] = data['station_name']

        if data['volume_remaining'] is None or data['volume_remaining'] < data['min_qty']:
            data['volume_state'] = 'danger'
        elif data['volume_remaining'] < data['min_qty'] * 1.2:
            data['volume_state'] = 'warning'
        else:
            data['volume_state'] = 'success'

        item = Item.objects.filter(id=data['item_id']).first()

        if item is not None:
            item.get_current_orders(
                ignore_seed_items=False,
                dest_station_id=data['station_id'],
                source_station_ids=[data['station_id']])

            ttl_price = 0
            ttl_qty = 0

            if data['station_id'] in item.z_orders:
                data['o'] = item.z_orders[data['station_id']]
                for o in data['o'].orders:
                    if ttl_qty < data['min_qty']:
                        qty = min(data['min_qty'] - ttl_qty, o.volume_remaining)
                        ttl_qty += qty
                        ttl_price += o.price * Decimal(qty)
                    else:
                        break
                if ttl_qty > 0:
                    data['avg_price'] = ttl_price / Decimal(ttl_qty)
            else:
                data['o'] = None


            data['thirtyday_vol'] = item.get_volume(region_id=data['region_id'], days=30)
            data['fiveday_vol'] = item.get_volume(region_id=data['region_id'], days=5)

        if not data['avg_price']:
            data['price_state'] = 'danger'
        elif data['twentypct_profit'] > 0:
                twentypct_profit = data['twentypct_profit']
                if twentypct_profit > data['avg_price']:
                    data['price_state'] = 'success'
                elif data['avg_price'] < float(twentypct_profit) * 1.1:
                    data['price_state'] = 'warning'
                else:
                    data['price_state'] = 'danger'
        else:
            data['price_state'] = 'success'

        if low_qty_only and 'state' not in data:
            continue

        if len(selected_stations) > 0 and data['station_id'] not in selected_stations:
            continue

        seed_items.append(data)

    out = render_page(
        'pgsus/seedview.html',
        dict(
            list=list,
            char_id=char_id,
            seed_data=seed_items,
            low_qty_only=low_qty_only,
            station=selected_stations,
            stations=stations,

        ),
        request
    )

    return out
