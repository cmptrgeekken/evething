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

from thing import queries

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8

from pgsus.parser import *

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

                    total_reward += entry['quantity'] * buyback_item.item.get_history_avg()
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
            pprinted=pprinted,
        ),
        request,
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