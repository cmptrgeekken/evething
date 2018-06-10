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

from thing.models import *  # NOPEP8
from thing.stuff import render_page, datetime  # NOPEP8
from django.shortcuts import redirect, render

from pgsus.parser import parse, iter_types
import evepaste


def index(request):
    return stats(request)

    # """Index page"""
    # tt = TimerThing('index')

    # profile = request.user.profile

    # tt.add_time('profile')

    # Render template
    # out = render_page(
    #    'pgsus/index.html',
    #    {
    #        'profile': 'hello!'
    #    },
    #    request,
    # )

    # tt.add_time('template')
    # if settings.DEBUG:
    #    tt.finished()

    # return out

def buyback(request, buyback_name):
    buyback = Buyback.objects.filter(slug=buyback_name).first()

    if not buyback:
        return redirect('/')

    parse_results = None
    buyback_input = ''

    if request.method == 'POST':
        buyback_input = request.POST.get('buyback_input')

        try:
            parse_results = parse(buyback_input)
        except evepaste.Unparsable:
            parse_results = None

    total_reward = 0
    total_volume = 0

    buyback_qty = dict()

    buyback_groups = BuybackItemGroup.objects.filter(buyback_id=buyback.id)

    latest_price = PriceHistory.objects.order_by('-date').first()
    price_last_updated = latest_price.date

    item_lookup = dict()

    for g in buyback_groups:
        for i in g.get_items():
            item_lookup[i.item.name.lower()] = i

    buyback_items = []

    if parse_results is not None:
        for kind, results in parse_results['results']:
            for entry in iter_types(kind, results):
                item_name = entry['name'].lower()

                if item_name in item_lookup:
                    buyback_item = item_lookup[item_name]
                    if buyback_qty.get(buyback_item.item.id) is None:
                        buyback_qty[buyback_item.item.id] = 0
                        buyback_items.append(buyback_item)
                    buyback_qty[buyback_item.item.id] += entry['quantity']

                    total_reward += entry['quantity'] * buyback_item.get_price()
                    total_volume += entry['quantity'] * buyback_item.item.volume
                else:
                    parse_results['bad_lines'].append(entry['name'])

    out = render_page(
        'pgsus/buyback2.html',
        dict(
            buyback_input=buyback_input,
            buyback_items=buyback_items,
            buyback=buyback,
            buyback_qty=buyback_qty,
            buyback_groups=buyback_groups,
            price_last_updated=price_last_updated,
            parse_results=parse_results,
            total_reward=total_reward,
            total_volume=total_volume,

        ),
        request,
    )

    return out


def _buyback(request):
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



