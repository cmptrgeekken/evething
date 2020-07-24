from thing.models import *  # NOPEP8
from thing.stuff import render_page
from thing.utils import dictfetchall
from thing import queries

import datetime

from django.shortcuts import redirect, render

from django.core.urlresolvers import reverse
from django.utils.text import slugify

from django.http import HttpResponse, JsonResponse

import json

from pgsus.parser import parse, iter_types
import evepaste


def contractadmin(request):
    if 'char' in request.session:
        char_id = request.session['char']['id']

        role = CharacterRole.objects.filter(character_id=char_id, role='contracts').first()
    else:
        role = None

    if role is None:
        return redirect('/')

    fits = request.POST.getlist('fit')

    if request.POST.get('move') == 'move':
        method = request.POST.get('move_method')
        target_station = request.POST.get('target_station')

        station = Station.objects.filter(id=target_station).first()

        if station is not None:
            station.load_market_orders = True
            station.market_profile_id = 96243993
            station.save()


        if method == 'move':
            rows = ContractSeeding.objects.filter(id__in=fits).update(station_id=target_station)

            return redirect('%s?msg=moved&count=%d' % (reverse(contractadmin), rows))
        elif method == 'copy':
            existing = ContractSeeding.objects.filter(id__in=fits)
            for e in existing:
                items = list(e.get_items())

                e.id = e.pk = None
                e.station_id = target_station
                e.current_qty = 0
                e.corp_qty = 0
                e.alliance_qty = 0
                e.save()

                for item in items:
                    item.id = item.pk = None
                    item.contractseeding_id = e.id
                    item.save()
            return redirect('%s?msg=copied&count=%d' % (reverse(contractadmin), len(existing)))

    if request.POST.get('delete') == 'delete':
        count = ContractSeeding.objects.filter(id__in=fits).count()

        ContractSeedingItem.objects.filter(contractseeding_id__in=fits).delete()
        ContractSeeding.objects.filter(id__in=fits).delete()

        return redirect('%s?msg=deleted&count=%d' % (reverse(contractadmin), count))
    
    if request.POST.get('activate') == 'activate':
        rows = ContractSeeding.objects.filter(id__in=fits).update(is_active=True)

        return redirect('%s?msg=activated&count=%d' % (reverse(contractadmin), rows))

    if request.POST.get('deactivate') == 'deactivate':
        rows = ContractSeeding.objects.filter(id__in=fits).update(is_active=False)

        return redirect('%s?msg=deactivated&count=%d' % (reverse(contractadmin), rows))

    active_seeding_entries = ContractSeeding.objects.filter(is_active=True, is_private=False).order_by('name')
    inactive_seeding_entries = ContractSeeding.objects.filter(is_active=False, is_private=False).order_by('name')

    station_entries = dict()
    for entry in active_seeding_entries:
        row = station_entries.setdefault(entry.station.name, {
            'station_id': entry.station_id,
            'station_name': entry.station.name,
            'active_count': 0, 
            'inactive_count': 0,
            'entries': []
        })

        entry.is_active = True

        row['active_count'] += 1

        row['entries'].append(entry)

    for entry in inactive_seeding_entries:
        row = station_entries.setdefault(entry.station.name, {
            'station_id': entry.station_id,
            'station_name': entry.station.name,
            'active_count': 0, 
            'inactive_count': 0,
            'entries': []
        })

        row['inactive_count'] += 1

        entry.is_active = False

        row['entries'].append(entry)

    message = None

    if request.GET.get('msg') is not None:
        msg = request.GET.get('msg')
        if msg in ['updated', 'deleted', 'deactivated', 'activated', 'copied', 'moved']:
            message = 'Successfully %s %d fits' % (msg, int(request.GET.get('count')))

    out = render_page(
        'pgsus/contractseedadmin.html',
        dict(
            station_entries=station_entries,
            message=message
        ),
        request
    )

    return out

def contractseedapi(request):
    data = dictfetchall("select c.id, c.name, c.current_qty, c.min_qty, s.name AS station_name, CASE WHEN priority = 0 THEN 'Low' WHEN priority = 1 THEN 'Medium' WHEN priority = 2 THEN 'High' END AS priority, c.qty_last_modified as last_updated from thing_contractseeding c inner join thing_station s on c.station_id=s.id where c.is_private=0 and c.is_active=1 order by s.name, c.priority DESC, c.name;")

    results = list()
    for d in data:
        d['last_updated'] = d['last_updated'].strftime('%Y-%m-%d %H:%M:%S')
        results.append(d)

    return HttpResponse(json.dumps(results), content_type='application/json')



"""
Displays all seeding lists associated to the currently logged-in user.
"""
def contractseedlist(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    char = Character.objects.filter(id=charid).first()

    public_lists = ContractSeeding.objects.filter(is_private=False, is_active=True).order_by('-station_id', '-priority', 'name')
    role = CharacterRole.objects.filter(character_id=charid, role='contracts').first()

    station_lists = dict()

    for l in public_lists:
        sname = l.station.short_name or l.station.name
        if sname not in station_lists:
            station_lists[sname] = []

        station_lists[sname].append(l)

    station_lists = station_lists.items()
    #station_lists.reverse()

    if request.GET.get('export') == 'json':
        slug = request.GET.get('slug')
        station_list = None
        for sname, l in station_lists:
            if slugify(sname) == slug:
                station_list = l
                break
        if station_list is not None:
            data = dict()

            data['station'] = sname
            data['fits'] = list()
            for l in station_list:
                entry = dict()
                entry['name'] = l.name
                entry['min_qty'] = l.min_qty
                if l.priority == 0:
                    entry['priority'] = 'Low'
                elif l.priority == 1:
                    entry['priority'] = 'Medium'
                else:
                    entry['priority'] = 'High'
                entry['last_updated'] = l.last_modified.strftime('%Y-%m-%d %H:%M:%S')
                entry['items'] = list()

                for i in l.get_items():
                    item = dict()
                    item['id'] = i.item.id

                    item['name'] = i.item.name
                    item['identifier'] = i.required
                    item['min_qty'] = i.min_qty

                    entry['items'].append(item)
                data['fits'].append(entry)
            return HttpResponse(json.dumps(data, indent=4), content_type='application/json')


    out = render_page(
        'pgsus/contractseedlist.html',
        dict(
            char_id=charid,
            station_lists=station_lists,
            is_admin=role is not None,
        ),
        request
    )

    return out


def contractseededit(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    char_id = request.session['char']['id']

    char = Character.objects.filter(id=char_id).first()

    role = CharacterRole.objects.filter(character_id=char_id, role='contracts').first()

    parse_results = None
    seed_input = ''
    min_qty = 1
    multiplier = 1

    stations = dict()

    station_list = Station.objects.filter(load_market_orders=True)
    for station in station_list:
        station.z_seed_selected = False
        stations[station.id] = station

    stations = [stations[id] for id in stations]

    stations.sort(key=lambda s: s.name)

    list = ContractSeeding(is_private=True)

    if request.GET.get('id') is not None:
        try:
            list_id = int(request.GET.get('id'))

            list = ContractSeeding.objects.filter(id=list_id)

            if role is None:
                list = list.filter(char_id=char_id)

            list = list.first()

            min_qty = list.min_qty

            for s in stations:
                if list.station_id == s.id:
                    s.z_seed_selected = True
                    break
        except Exception:
            list = None

        if list is None:
            return redirect(reverse(contractseedlist))

    if request.method == 'POST':
        updateMethod = request.POST.get('method')

        if updateMethod == 'update':
            list.name = request.POST.get('list_name')
            list.char_id = char_id
            list.corp_id = 98388312 # TODO: Don't hard-code
            list.station_id = request.POST.get('station_id')
            list.min_qty = request.POST.get('min_qty')
            list.is_private = request.POST.get('private') == 'Y'
            list.priority = request.POST.get('priority')

            do_redirect = True

            if list.raw_text != request.POST.get('raw_text')\
                    and request.POST.get('raw_text') is not None:
                list.raw_text = request.POST.get('raw_text')

                seed_input = request.POST.get('raw_text')

                try:
                    parse_results = parse(seed_input)
                except evepaste.Unparsable:
                    parse_results = None

                if parse_results is not None:
                    seen_items = dict()
                    for kind, results in parse_results['results']:
                        for entry in iter_types(kind, results):
                            monitor_item = Item.objects.filter(
                                name__iexact=entry['name']
                            ).first()

                            if monitor_item is not None:
                                min_qty = entry['quantity']

                                if monitor_item.id in seen_items:
                                    existing_item = seen_items[monitor_item.id]
                                    existing_item.min_qty += min_qty
                                else:
                                    reqd = monitor_item.item_group.category.name == 'Ship'

                                    seeditem = ContractSeedingItem(
                                        contractseeding_id=list.id,
                                        item_id=monitor_item.id,
                                        min_qty=min_qty,
                                        required=reqd,
                                    )

                                    seen_items[monitor_item.id] = seeditem
                            else:
                                parse_results['bad_lines'].append(entry['name'])

                    if list.id > 0:
                        ContractSeedingItem.objects.filter(contractseeding_id=list.id).delete()

                    for i in seen_items.values():
                        i.save()

                    if len(parse_results['bad_lines']) > 0:
                        do_redirect = False

            list.save()

            update_list(list, char_id)


            if do_redirect:
                return redirect('%s?id=%d' % (reverse(contractseededit), list.id))

        if updateMethod == "delete":
            list.get_items().delete()
            list.delete()

            return redirect(reverse(contractseedlist))

        if updateMethod == "manageitems":
            del_ids = request.POST.getlist('del_id')
            reqd_ids = request.POST.getlist('reqd_id')

            ids = request.POST.getlist('seed_id')
            qties = request.POST.getlist('min_qty')

            for i in range(0, len(ids)):
                id = ids[i]
                qty = qties[i]

                seeditem = ContractSeedingItem.objects.filter(id=id, contractseeding_id=list.id).first()

                if seeditem is not None:
                    seeditem.min_qty = qty
                    seeditem.save()

            if len(reqd_ids) > 0:
                ContractSeedingItem.objects.filter(id__in=reqd_ids).update(required=True)
                ContractSeedingItem.objects.filter(contractseeding_id=list.id).exclude(id__in=reqd_ids).update(required=False)

            if len(del_ids) > 0:
                ContractSeedingItem.objects.filter(id__in=del_ids).delete()
            
            update_list(list, char_id)

            return redirect('%s?id=%d' % (reverse(contractseededit), list.id))

    seeditems = list.get_items()

    out = render_page(
        'pgsus/contractseededit.html',
        dict(
            seed_input=seed_input,
            stations=stations,
            list=list,
            seeditems=seeditems,
            min_qty=min_qty,
            parse_results=parse_results,
            multiplier=multiplier,
            priorities=ContractSeeding.PRIORITIES,
        ),
        request
    )

    return out

def update_list(list, char_id):
    list.estd_price = list.get_estd_price()
    list.current_qty = list.get_stock_count()
    list.corp_qty = list.get_corp_stock()
    list.alliance_qty = list.get_alliance_stock()
    list.qty_last_modified = datetime.datetime.now()
    list.last_modified = datetime.datetime.now()
    list.last_modified_by_id = char_id
    list.save()


def contractseedview(request):
    if 'char' in request.session:
        char_id = request.session['char']['id']

        role = CharacterRole.objects.filter(character_id=char_id, role='contracts').first()
        open_window_scope = CharacterApiScope.objects.filter(character_id=char_id, scope='esi-ui.open_window.v1').first()
    else:
        char_id = None
        role = None
        open_window_scope = None

    list_id = request.GET.get('id')

    page = int(request.GET.get('page') or 1)

    list = ContractSeeding.objects.filter(id=list_id).first()

    if list is None:
        return redirect('/?login=1')

    related_contracts, ttl_pages = list.get_stock(page=page)

    item_lookup = dict()

    for item in list.get_items():
        item_lookup[item.item_id] = item

    ttl_items = len(item_lookup.keys())

    for c in related_contracts:
        c_items = c.get_items()

        c_matching_ct = 0

        c_extra_items = []
        c_missing_items = []

        c_item_lookup = dict()

        for c_item in c_items:
            c_item_lookup[c_item.item_id] = c_item

        for id, item in item_lookup.items():
            if id not in c_item_lookup:
                c_missing_items.append(dict(name=item.item.name, missing_qty=item.min_qty))
            elif c_item_lookup[id].quantity < item.min_qty:
                c_missing_items.append(dict(name=item.item.name, missing_qty=item.min_qty - c_item_lookup[id].quantity))
            else:
                c_matching_ct += 1

        for id, c_item in c_item_lookup.items():
            if id not in item_lookup:
                c_extra_items.append(dict(name=c_item.item.name, extra_qty=c_item.quantity))

        c.z_matching_pct = float(c_matching_ct) / ttl_items
        c.z_missing_items = c_missing_items
        c.z_extra_items = c_extra_items

    def contract_sort(a, b):
        return -1 if a.price < b.price else 1

    related_contracts.sort(contract_sort)

    out = render_page(
        'pgsus/contractseedview.html',
        dict(
            list=list,
            item_lookup=item_lookup,
            ttl_pages=ttl_pages,
            current_page=page,
            related_contracts=related_contracts,
            char_id=char_id,
            is_admin=role is not None,
            open_window=open_window_scope is not None,
            page_path=request.get_full_path()
        ),
        request
    )

    return out
