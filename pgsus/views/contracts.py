from thing.models import *  # NOPEP8
from thing.stuff import render_page
from thing.utils import dictfetchall
from thing.helpers import timeago, humanize
from thing import queries

from django.http import JsonResponse

from decimal import Decimal

def publiccontracts(request):
    out = render_page(
        'pgsus/publiccontracts.html',
        dict(),
        request
    )

    return out

def api_regions(request):
    name = request.GET.get('term')

    regions = list()
    if len(name) >= 3:
        regions = Region.objects.filter(name__istartswith=name)

    return JsonResponse(
        dict(
            response=[{'id': r.id, 'name': r.name} for r in regions]
        )
    )

def api_locations(request):
    name = request.GET.get('term')

    locations = list()
    if len(name) >= 3:
        locations = MapDenormalize.objects.filter(item_name__icontains=name, type_id__in=[3,4,5])

    return JsonResponse(
        dict(
            response=[{'id': l.item_id, 'name': l.item_name} for l in locations]
        )
    )
    

def api_issuer_char_ids(request):
    name = request.GET.get('term')

    chars = list()
    if len(name) >= 3:
        chars = Character.objects.filter(name__istartswith=name)

    return JsonResponse(
        dict(
            response=[{'id': c.id, 'name': c.name } for c in chars]
        )
    )

def api_issuers(request):
    name = request.GET.get('term')

    issuers = list()

    if len(name) >= 3:
        corps = Corporation.objects.filter(name__istartswith=name)
        chars = Character.objects.filter(name__istartswith=name)
        issuers = [c for c in corps] + [c for c in chars]

    return JsonResponse(
        dict(
            response=[{'id': i.id, 'name': i.name } for i in issuers]
        )
    )

def api_categories(request):
    name = request.GET.get('term')


    if not name:
        categories = ItemCategory.objects.all().order_by('name')
    else:
        categories = ItemCategory.objects.filter(name__istartswith=name).order_by('name')

    return JsonResponse(
        dict(
            response=[{'id': c.id, 'name': c.name} for c in categories]
        )
    )

def api_groups(request):
    name = request.GET.get('term')
    category_id = request.GET.get('category_id')

    if not name:
        groups = ItemGroup.objects.filter(category_id=category_id).order_by('name')
    else:
        groups = ItemGroup.objects.filter(name__istartswith=name, category_id=category_id).order_by('name')

    return JsonResponse(
        dict(
            response=[{'id': g.id, 'name': g.name} for g in groups]
        )
    )

def api_items(request):
    name = request.GET.get('term')

    items = list()
    if len(name) >= 3:
        items = Item.objects.filter(name__icontains=name)

    return JsonResponse(
        dict(
            response=[{'id': i.id, 'name': i.name } for i in items]
        )
    )

def api_publiccontracts(request):
    contracts = PublicContract.objects.all()

    region_id = int(request.GET.get('region_id')) if request.GET.get('region_id') else None
    constellation_id = int(request.GET.get('constellation_id')) if request.GET.get('constellation_id') else None
    system_id = int(request.GET.get('system_id')) if request.GET.get('system_id') else None

    location_id = int(request.GET.get('location_id')) if request.GET.get('location_id') else None

    contract_type = request.GET.get('contract_type')

    item_id = int(request.GET.get('item_id')) if request.GET.get('item_id') else None
    type_id = int(request.GET.get('type_id')) if request.GET.get('type_id') else None
    category_id = int(request.GET.get('category_id')) if request.GET.get('category_id') else None
    group_id = int(request.GET.get('group_id')) if request.GET.get('group_id') else None

    exact_name = request.GET.get('exact_name') == '1'

    if location_id is not None:
        location = MapDenormalize.objects.filter(item_id=location_id).first()

        if location is not None:
            if location.type_id == 3: # Region
                region_id = location_id
            elif location.type_id == 4: # Constellation
                constellation_id = location_id
            elif location.type_id == 5:
                system_id = location_id

    type_ids = list()
    if type_id is None:
        the_type = request.GET.get('type')
        if the_type is not None:
            if exact_name:
                types = Item.objects.filter(name=the_type)
            else:
                types = Item.objects.filter(name__contains=the_type)
            type_ids = [t.id for t in types]
    else:
        type_ids = [type_id]

    if category_id is None:
        category = request.GET.get('category')
        if category is not None:
            category = ItemCategory.objects.filter(name=category).first()

            if category is not None:
                category_id = category.id

    if request.GET.get('only_bpo'):
        is_bpo = True
    elif request.GET.get('only_bpc'):
        is_bpo = False
    else:
        is_bpo = None

    min_me = int(request.GET.get('min_me')) if request.GET.get('min_me') else 0
    max_me = int(request.GET.get('max_me')) if request.GET.get('max_me') else None
    min_te = int(request.GET.get('min_te')) if request.GET.get('min_te') else 0
    max_te = int(request.GET.get('max_te')) if request.GET.get('max_te') else None
    min_runs = int(request.GET.get('min_runs')) if request.GET.get('min_runs') else 0
    exclude_multiple = request.GET.get('exclude_multiple') == '1' or request.GET.get('single') == '1'

    issuer_corp_id = int(request.GET.get('issuer_corp_id')) if request.GET.get('issuer_corp_id') else None
    issuer_char_id = int(request.GET.get('issuer_char_id')) if request.GET.get('issuer_char_id') else None

    issuer_id = int(request.GET.get('issuer_id')) if request.GET.get('issuer_id') else None

    min_price = Decimal(request.GET.get('min_price')) * 1000000 if request.GET.get('min_price') else Decimal(0)
    max_price = Decimal(request.GET.get('max_price')) * 1000000 if request.GET.get('max_price') else None

    min_reward = Decimal(request.GET.get('min_reward')) * 1000000 if request.GET.get('min_reward') else Decimal(0)
    max_reward = Decimal(request.GET.get('max_reward')) * 1000000 if request.GET.get('max_reward') else None

    min_collateral = Decimal(request.GET.get('min_collateral')) * 1000000 if request.GET.get('min_collateral') else Decimal(0)
    max_collateral = Decimal(request.GET.get('max_collateral')) * 1000000 if request.GET.get('max_collateral') else None

    page_size = min(max(5, int(request.GET.get('page_size')) if request.GET.get('page_size') else 100), 1000)
    current_page = max(1, int(request.GET.get('page')) if request.GET.get('page') else  1)

    security_high = request.GET.get('security_high') == '1'
    security_low = request.GET.get('security_low') == '1'
    security_null = request.GET.get('security_null') == '1'

    order = request.GET.get('order')

    status = request.GET.get('contract_status') or 'outstanding'

    parms = list()

    qry = 'SELECT DISTINCT pc.id FROM thing_publiccontractitem pci'\
            + ' INNER JOIN thing_publiccontract pc ON pci.contract_id=pc.id'\
            + ' LEFT JOIN thing_station st ON pc.start_station_id=st.id'\
            + ' LEFT JOIN thing_item i ON pci.type_id=i.id'\
            + ' LEFT JOIN thing_itemgroup ig ON i.item_group_id=ig.id'\
            + ' LEFT JOIN thing_itemcategory ic ON ig.category_id=ic.id'\
            + ' LEFT JOIN thing_system sy ON st.system_id=sy.id'\
            + ' LEFT JOIN thing_mapdenormalize md ON sy.id = md.item_id'\
            + ' WHERE 1=1'

    if type_ids:
        qry += ' AND pci.type_id IN ('
        for i in type_ids:
            qry += '%s,'
            parms.append(i)
        qry = qry.rstrip(',') + ')'

    if group_id:
        qry += ' AND i.item_group_id = %s'
        parms.append(group_id)
    elif category_id:
        qry += ' AND ic.id = %s'
        parms.append(category_id)

    if item_id:
        qry += ' AND pci.item_id = %s'
        parms.append(item_id)

    if min_me > 0:
        qry += ' AND pci.material_efficiency >= %s'
        parms.append(min_me)

    if max_me:
        qry += ' AND pci.material_effiency <= %s'
        parms.append(max_me)

    if min_te > 0:
        qry += ' AND pci.time_efficiency >= %s'
        parms.append(min_te)
    
    if max_te:
        qry += ' AND pci.time_efficiency <= %s'
        parms.append(max_te)
    
    if min_runs > 0:
        qry += ' AND pci.runs >= %s'
        parms.append(min_runs)
    
    if is_bpo is not None:
        qry += ' AND pci.is_blueprint_copy=%s'
        parms.append(0 if is_bpo else 1)

    if region_id:
        qry += ' AND region_id=%s'
        parms.append(region_id)

    if constellation_id:
        qry += ' AND sy.constellation_id=%s'
        parms.append(constellation_id)

    if system_id:
        qry += ' AND sy.id=%s'
        parms.append(system_id)

    if min_price > 0:
        qry += ' AND pc.price >= %s'
        parms.append(min_price)

    if max_price:
        qry += ' AND pc.price <= %s'
        parms.append(max_price)

    if min_reward > 0:
        qry += ' AND reward >= %s'
        parms.append(min_reward)

    if max_reward:
        qry += ' AND reward <= %s'
        parms.append(max_reward)

    if min_collateral:
        qry += ' AND collateral >= %s'
        parms.append(min_collateral)

    if max_collateral:
        qry += ' AND collateral <= %s'
        parms.append(max_collateral)

    if issuer_corp_id:
        qry += ' AND issuer_corp_id=%s'
        parms.append(issuer_corp_id)

    if issuer_char_id:
        qry += ' AND issuer_char_id=%s'
        parms.append(issuer_char_id)

    if issuer_id is not None:
        qry += ' AND (issuer_char_id=%s OR issuer_corp_id=%s)'
        parms.append(issuer_id)
        parms.append(issuer_id)

    if contract_type == 'exclude_wtb' or contract_type == 'wts':
        qry += ' AND pci.included=1'
    elif contract_type in ['item_exchange', 'auction', 'courier']:
        qry += ' AND pc.type=%s'
        parms.append(contract_type)
    elif contract_type == 'wtb':
        qry += ' AND pci.included=0'

    if security_high or security_low or security_null:
        sec_status = []
        if security_high:
            sec_status.append('md.security >= 5')
        if security_low:
            sec_status.append('md.security > 0 AND md.security < 5')
        if security_null:
            sec_status.append('md.security <= 0')

        qry += ' AND (%s)' % ' OR '.join(sec_status)

    if exclude_multiple:
        qry += ' AND EXISTS (SELECT 1 FROM thing_publiccontractitem pci2 WHERE pci2.contract_id=pci.contract_id GROUP BY pci.contract_id HAVING COUNT(*)=1)'

    # TODO: Status
    if status == 'outstanding':
        qry += ' AND pc.status=\'outstanding\''
    elif status == 'maybe_expired':
        qry += ' AND DATE_ADD(pc.date_expired, INTERVAL -3 HOUR) < pc.date_lastseen'
        pass
    elif status == 'maybe_fulfilled':
        qry += ' AND (pc.status=\'maybe_fulfilled\' OR (pc.status=\'unknown\' AND DATE_ADD(pc.date_expired, INTERVAL -1 DAY) > pc.date_lastseen))'
    elif status != 'all':
        # contracts = contracts.filter(status=status)
        pass

    if contract_type != 'courier':
        orders = {
            'price_asc': 'pc.price ASC',
            'price_desc': 'pc.price DESC',
            'issued_asc': 'pc.date_issued ASC',
            'issued_desc': 'pc.date_issued DESC',
            'time_left_asc': 'pc.date_expired ASC',
            'time_left_desc': 'pc.date_expired DESC'
        }
    else:
        orders = {
            'issued_asc': 'pc.date_issued ASC',
            'issued_desc': 'pc.date_issued DESC',
            'collateral_asc': 'pc.collateral ASC',
            'collateral_desc': 'pc.collateral DESC',
            'reward_asc': 'pc.reward ASC',
            'reward_desc': 'pc.reward DESC',
            'volume_asc': 'pc.volume ASC',
            'volume_desc': 'pc.volume DESC'
        }

    if order and order in orders:
        qry += ' ORDER BY %s' % orders[order]
    else:
        qry += ' ORDER BY pc.date_issued DESC'

    # Paginate
    qry += ' LIMIT %s, %s'
    parms.append((current_page-1)*page_size)
    parms.append(page_size+1)

    id_result = dictfetchall(qry, parms=parms)
    ids = [r['id'] for r in id_result]

    contractitems = PublicContractItem.objects.select_related('type', 'type__item_group', 'type__item_group__category').filter(contract_id__in=ids)
    ci_lookup = {}
    for ci in contractitems:
        ci_lookup.setdefault(ci.contract_id, []).append(ci)

    contracts = PublicContract.objects.select_related(
        'issuer_char', 
        'issuer_corp', 
        'start_station', 
        'start_station__system',
        'start_station__system__constellation', 
        'end_station',
        'end_station__system',
        'end_station__system__constellation',
        'end_station__system__constellation__region'
    ).filter(id__in=ids)

    # Filter Contract Items after
    entries = list()
    for c in contracts[0:page_size]:
        items = list()

        if c.id in ci_lookup:
            for i in ci_lookup[c.id]:
                item = {
                    'record_id': i.record_id,
                    'type_id': i.type_id,
                    'type_name': i.type.name if i.type is not None else None,
                    'group_id': i.type.item_group_id,
                    'group_name': i.type.item_group.name,
                    'category_id': i.type.item_group.category_id,
                    'category_name': i.type.item_group.category.name,
                    'quantity': i.quantity,
                    'included': i.included,
                    'is_blueprint': i.type.name.endswith('Blueprint')
                }

                if item['is_blueprint']:
                    item['is_blueprint_copy'] = True if i.is_blueprint_copy else False
                    item['me'] = i.material_efficiency
                    item['te'] = i.time_efficiency
                    item['icon'] = 'https://images.evetech.net/types/%s/%s?size=32' % (item['type_id'], 'bpc' if item['is_blueprint_copy'] else 'bp')

                    if item['is_blueprint_copy']:
                        item['runs'] = i.runs
                else:
                    item['icon'] = 'https://images.evetech.net/types/%s/icon?size=32' % (item['type_id'])


                items.append(item)

        entry = {
            'id': c.contract_id,
            'issuer_char_id': c.issuer_char_id,
            'issuer_char_name': c.issuer_char.name if c.issuer_char_id is not None else None,
            'issuer_corp_id': c.issuer_corp_id,
            'issuer_corp_name': c.issuer_corp.name if c.issuer_corp_id is not None else None,
            'start_region_id': c.region_id,
            'start_region_name': c.region.name,
            'end_region_id': c.end_station.system.constellation.region_id if c.end_station and c.end_station.system is not None else None,
            'end_region_name': c.end_station.system.constellation.region.name if c.end_station and c.end_station.system is not None else None,
            'start_station_id': c.start_station_id,
            'start_station_name': c.start_station.name if c.start_station and c.start_station.system else None,
            'start_system_name': c.start_station.system.name if c.start_station and c.start_station.system else None,
            'end_station_id': c.end_station_id,
            'end_station_name': c.end_station.name if c.end_station and c.end_station.system is not None else None,
            'end_system_name': c.end_station.system.name if c.end_station and c.end_station.system else None,
            'type': c.type,
            'status': c.status,
            'title': c.title,
            'for_corp': c.for_corp,
            'date_issued': c.date_issued,
            'date_expired': c.date_expired,
            'date_lastseen': c.date_lastseen,
            'num_days': c.num_days,
            'price': c.price,
            'reward': c.reward,
            'buyout': c.buyout,
            'volume': c.volume,
            'collateral': c.collateral
        }

        if items:
            entry['items'] = items
            wtb = filter(lambda i: not i['included'], items)
            wts = filter(lambda i: i['included'], items)
            entry['items_requested'] = wtb
            entry['items_offered'] = wts
            entry['item_count'] = len(items)
            entry['items_requested_count'] = len(wtb)
            entry['items_offered_count'] = len(wts)
            entry['single_item_requested'] = len(wtb) == 1

            if len(wtb) > 0 and len(wts) > 0:
                entry['offer_type'] = 'wtt'
            elif len(wtb) > 0:
                entry['offer_type'] = 'wtb'
            else:
                entry['offer_type'] = 'wts'

            if len(wtb) == 1:
                entry['wtb_single'] = True
                item = wtb[0]
                entry['wtb_item'] = item
            elif len(wtb) > 1:
                entry['wtb_multiple'] = True


            if len(wts) == 1:
                entry['wts_single'] = True
                item = wts[0]
                entry['wts_item'] = item
            else:
                entry['wts_single'] = False

            entry['date_expired_fmt'] = timeago(entry['date_expired'])
            entry['date_lastseen_fmt'] = timeago(entry['date_lastseen'])
            entry['date_issued_short'] = entry['date_issued'].strftime('%Y-%m-%d')
            entry['has_price'] = entry['price'] > 0
            entry['has_reward'] = entry['reward'] > 0
            entry['price_humanized'] = humanize(entry['price'])
            entry['reward_humanized'] = humanize(entry['reward'])
            entry['collateral_humanized'] = humanize(entry['collateral'])
            entry['buyout_humanized'] = humanize(entry['buyout'])
        
        entries.append(entry)
        
    return JsonResponse(dict(
        more=len(contracts) > page_size,
        contracts=entries,
        page_size=page_size,
        page=current_page,
        results_shown=len(entries)
    ))

