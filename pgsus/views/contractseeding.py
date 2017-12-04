from thing.models import *  # NOPEP8
from thing.stuff import render_page
from thing.utils import dictfetchall
from thing import queries

from django.shortcuts import redirect, render

from django.core.urlresolvers import reverse

from pgsus.parser import parse, iter_types
import evepaste


"""
Displays all seeding lists associated to the currently logged-in user.
"""
def contractseedlist(request):
    if 'char' not in request.session:
        return redirect('/')

    charid = request.session['char']['id']

    lists = ContractSeeding.objects.filter  (char_id=charid)

    char = Character.objects.filter(id=charid).first()

    public_lists = ContractSeeding.objects.filter(is_private=False, corp_id=char.corporation_id)

    station_lists = dict()

    for list in public_lists:
        if list.station.name not in station_lists:
            station_lists[list.station.name] = []

        station_lists[list.station.name].append(list)

    out = render_page(
        'pgsus/contractseedlist.html',
        dict(
            seed_lists=lists,
            station_lists=station_lists,
        ),
        request
    )

    return out


def contractseededit(request):
    if 'char' not in request.session:
        return redirect('/')

    char_id = request.session['char']['id']

    char = Character.objects.filter(id=char_id).first()

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

            list = ContractSeeding.objects.filter(id=list_id, char_id=char_id).first()

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
            list.corp_id = char.corporation_id
            list.station_id = request.POST.get('station_id')
            list.min_qty = request.POST.get('min_qty')
            list.is_private = request.POST.get('private') == 'Y'

            do_redirect = True

            if list.raw_text != request.POST.get('raw_text'):
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
        ),
        request
    )

    return out


def contractseedview(request):
    if 'char' in request.session:
        char_id = request.session['char']['id']
    else:
        char_id = None

    list_id = request.GET.get('id')

    list = ContractSeeding.objects.filter(id=list_id).first()

    if list is None or (list.is_private and list.char_id != char_id):
        return redirect('/')

    out = render_page(
        'pgsus/contractseedview.html',
        dict(
            list=list,
            char_id=char_id,
        ),
        request
    )

    return out
