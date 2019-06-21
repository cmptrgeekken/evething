from thing.models import *  # NOPEP8
from thing.stuff import render_page
from thing.utils import dictfetchall
from thing import queries

from django.shortcuts import redirect, render

from django.core.urlresolvers import reverse

from django.core import serializers

from django.http import JsonResponse

from pgsus.parser import parse, iter_types
import evepaste


def api_publiccontracts(request):
    contracts = PublicContract.objects.all()

    region_id = request.GET.get('region')
    system_id = request.GET.get('system')

    item_id = request.GET.get('item')
    category = request.GET.get('category')

    is_bpo = request.GET.get('bpo') == 1
    min_me = request.GET.get('min_me')
    max_me = request.GET.get('max_me')
    min_te = request.GET.get('min_te')
    max_te = request.GET.get('max_te')
    min_runs = request.GET.get('min_runs')
    exclude_multiple = request.GET.get('exclude_multiple')

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    issuer_corp = request.GET.get('issuer_corp')
    issuer_char = request.GET.get('issuer_char')

    min_reward = request.GET.get('min_reward')
    max_reward = request.GET.get('max_reward')

    min_collateral = request.GET.get('min_collateral')
    max_collateral = request.GET.get('max_collateral')

    page_size = min(max(5, request.GET.get('page_size') or 100), 500)
    current_page = max(1, request.GET.get('page') or 1)

    order = request.GET.get('order')

    status = request.GET.get('status') or 'outstanding'

    if region_id:
        contracts = contracts.filter(region_id=region_id)

    if system_id:
        contracts = contracts.filter(start_station__system_id=system_id)

    if min_price:
        contracts = contracts.filter(price__gte=min_price)

    if max_price:
        contracts = contracts.filter(price__lte=max_price)

    if issuer_corp:
        contracts = contracts.filter(issuer_corp_id=issuer_corp)

    if issuer_char:
        contracts = contracts.filter(issuer_char_id=issuer_char)

    if min_reward:
        contracts = contracts.filter(reward__gte=min_reward)

    if max_reward:
        contracts = contracts.filter(reward__lte=max_reward)

    if min_collateral:
        contracts = contracts.filter(collateral__gte=min_collateral)

    if max_collateral:
        contracts = contracts.filter(collateral__lte=max_collateral)


    if status == 'completed':
        contracts = contracts.filter(status='unknown')
    if status != 'all':
        contracts = contracts.filter(status=status)

    if order:
        contracts = contracts.order_by(order)
    else:
        contracts = contracts.order_by('-date_issued')

    pages = len(contracts) / page_size

    contracts = contracts[(current_page-1)*page_size:current_page*page_size-1]


    # Filter Contract Items after
        
    return JsonResponse(dict(
        pages=pages,
        contracts=serializers.serialize('json', contracts)
    ))

