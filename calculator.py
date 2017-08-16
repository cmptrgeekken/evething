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

import os
# Set up our environment and import settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
import django
django.setup()

from thing.models import *  # NOPEP8

import math
from decimal import *

from lpsolve55 import *
from django.db.models import Min

def calculator():
    # minerals = ['trit', 'pye', 'mex', 'iso', 'nocx', 'zyd', 'mega', 'morp']#, 'hw', 'stront', 'lo', 'hel', 'hyd', 'nit', 'oxy']
    mineralids = [34, 35, 36, 37, 38, 39, 40, 11399] #, 16272, 16275, 16273, 16274, 17889, 17888, 17887]
    requirements = [282310765, 69412900, 25902055, 4050955, 1144765, 410270, 176730, 0] #, 0, 0, 0, 0, 0, 0, 0]
    overage = [0, 0, 0, 0, 0, 0, 0, 0]#, 0, 0, 0, 0, 0, 0, 0]

    minidlookup = dict()
    for i in range(0, len(mineralids)):
        minidlookup[mineralids[i]] = i

    items = []
    item_maxes = []
    items_query = Item.objects.filter(name__iregex='^Compressed', item_group__category__name='Asteroid').exclude(item_group__name='Ice')

    idx = 0
    for item in items_query:
        min_base = Item.objects.filter(name__iregex='^Compressed', item_group__name=item.item_group.name).aggregate(price=Min('base_price'))['price']
        if item.base_price == min_base:
            item.z_reprocessed_items = item.get_reprocessed_items()

            mineral_value = 0
            max_qty = 0

            has_mineral = False

            for mineral in item.z_reprocessed_items:
                idx = minidlookup[mineral.id]
                repro_qty = float(mineral.z_qty) * .875
                mineral_value += float(mineral.sell_fivepct_price) * repro_qty
                max_qty = max(max_qty, int(requirements[idx]) / int(repro_qty))
                if requirements[idx] > 0:
                    has_mineral = True

            if not has_mineral:
                continue

            item.z_index = idx
            items.append(item)
            idx = idx + 1

            item.z_mineral_value = mineral_value
            item.z_mineral_ratio = float(item.sell_fivepct_price) / mineral_value

            related_items = Item.objects.filter(item_group_id=item.item_group.id, name__iregex='^Compressed')

            item.z_related_ids = [i.id for i in related_items]

            max_order_qty = item.get_max_order_volume(item_ids=item.z_related_ids)

            item.z_max_qty = min(max_qty, max_order_qty)

            # TODO: Properly calculate shipping?
            item.z_total_price = int(float(item.sell_fivepct_price)*1.15 + float(item.volume*290))

            item_maxes.append(item.z_max_qty)

    ttl_price_obj_fn = [i.z_total_price for i in items]
    base_price_obj_fn = [i.base_price for i in items]
    volume_obj_fn = [i.volume for i in items]

    obj_fns = [
        ttl_price_obj_fn,
        base_price_obj_fn,
        volume_obj_fn,
    ]

    for obj_fn in obj_fns:
        results = solve(obj_fn, mineralids, requirements, overage, items, item_maxes)

        if results is not None:
            all_orders, full_price_best, full_price_multibuy, fulfilled_all = results

            if not fulfilled_all:
                print("Not all results could be fulfilled!")
            else:
                print "Best: %d, Multi: %d" % (full_price_best, full_price_multibuy)
            break


def solve(obj_fn, mineralids, requirements, overage, items, item_maxes, timeout=10):
    lp = lpsolve('make_lp', 0, len(items))

    # Timeout after 10s
    ret = lpsolve('set_timeout', lp, timeout)

    lpsolve('set_verbose', lp, IMPORTANT)

    max_quantities = [0] * len(requirements)
    for i in range(0, len(requirements)):
        if overage[i] > 0:
            max_quantities[i] = requirements[i] + overage[i]

    ret = lpsolve('set_obj_fn', lp, obj_fn)

    for col in range(1, len(items) + 1):
        lpsolve('set_int', lp, col, 1)

    for item in items:
        item.z_reprocessed = item.get_reprocessed_items()

    for minid in range(0, len(mineralids)):
        numbers = []
        for item in items:
            # TODO: Remove nested loops!
            found = False
            for min in item.z_reprocessed:
                if min.id == mineralids[minid]:
                    qty = math.floor(min.z_qty * .875)  # Don't hard-code of course
                    numbers.append(qty)
                    found = True
                    break
            if not found:
                numbers.append(0)

        ret = lpsolve('add_constraint', lp, numbers, GE, requirements[minid])

        if overage[minid] > 0:
            ret = lpsolve('add_constraint', lp, numbers, LE, max_quantities[minid])

    ret = lpsolve('set_lowbo', lp, [0] * len(items))

    ret = lpsolve('set_upbo', lp, item_maxes)

    solution = lpsolve('solve', lp)
    x = lpsolve('get_variables', lp)

    lpsolve('delete_lp', lp)

    items_to_buy = []
    if solution == 0:
        min_qty = [0] * len(mineralids)

        for i in range(0, len(x[0])):
            item = items[i]
            qty = x[0][i]
            if qty > 0:
                item.z_qty_to_buy = qty
                items_to_buy.append(item)
                for sub in item.z_reprocessed:
                    for idx in range(0, len(mineralids)):
                        if sub.id == mineralids[idx]:
                            min_qty[idx] += qty * sub.z_qty * .875

        full_price_best = 0
        full_price_multibuy = 0

        all_orders = []

        fulfilled_all = True

        for item in items_to_buy:
            qty = item.z_qty_to_buy

            item_orders, ttl_price_best, ttl_price_multibuy, last_updated, qty_remaining, station_ct = item.get_current_orders(
                qty,
                item_ids=item.z_related_ids)

            full_price_best += ttl_price_best
            full_price_multibuy += ttl_price_multibuy

            if qty_remaining > 0:
                fulfilled_all = False
                print("Not fulfilled: %s, short: %d out of %d" % (item.item_group.name, qty_remaining, qty))

            for o in item_orders:
                if o.z_order_qty > 0:
                    all_orders.append(o)

        return all_orders, full_price_best, full_price_multibuy, fulfilled_all

    return None


if __name__ == '__main__':

    calculator()
