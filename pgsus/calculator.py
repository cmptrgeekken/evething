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

from thing.models import *  # NOPEP8

import math

from decimal import Decimal

from django.db.models import Min

from lpsolve55 import *


class Calculator:
    def __init__(self):
        return

    OPTIMIZATION_PRICE = 1
    OPTIMIZATION_VOLUME = 2

    """
    As we can't use the ice group name to determine related ice items, we must
    hard-code the ices and their related values
    """
    COMPRESSED_ICES = dict([
        (28433, [28433, 28443]),
        (28434, [28434, 28436]),
        (28435, [28435]),
        (28437, [28437]),
        (28438, [28438, 28442]),
        (28439, [28439]),
        (28440, [28440]),
        (28444, [28444, 28441])
    ])

    """
        target_minerals: dict(mineral_id=>qty)
            - List of desired minerals. The generated outcome will optimize the cost
        max_mineral_overages: dict(mineral_id=>qty)
            - List of the maximum allowed overage of minerals. If not specified, will optimize ores without regard
              to overage.
        allow_mineral_purchase: Boolean
            - If true, minerals will be included in the optimization strategy
        optimization_strategy: OPTIMIZATION_PRICE | OPTIMIZATION_VOLUME
            - Strategy to use for optimizing. If PRICE, will minimize the cost, taking shipping into consideration.
              If VOLUME, optimization will be minimize overall volume. 
        source_station_ids: [station_id]
            - Represents the list of stations where minerals and / or ores can be sourced from. This will be used to
              determine the best location for purchasing the minerals or ores
        dest_station_id: station_id
            - ID of the station where the minerals / ores are required
    """
    def calculate_optimal_ores(self, target_minerals, max_mineral_overages=None, allow_mineral_purchase=True, optimization_strategy=OPTIMIZATION_PRICE, source_station_ids=None, dest_station_id=None, reprocess_pct=0.875):
        mineralids = target_minerals.keys()
        requirements = target_minerals.values()
        overage = [max_mineral_overages[key]
                    if max_mineral_overages is not None and key in max_mineral_overages else 0
                    for key in mineralids]

        minidlookup = dict()
        for i in range(0, len(mineralids)):
            minidlookup[mineralids[i]] = i

        items = []
        item_maxes = []

        items_query = Item.objects.filter(name__iregex='^Compressed', item_group__category__name='Asteroid')

        idx = 0
        for item in items_query:
            min_base = Item.objects.filter(name__iregex='^Compressed', item_group__name=item.item_group.name).aggregate(
                price=Min('base_price'))['price']

            if (item.item_group.name == 'Ice' and item.id in self.COMPRESSED_ICES) or item.base_price == min_base:
                item.z_reprocessed_items = item.get_reprocessed_items()

                mineral_value = 0
                max_qty = 0

                has_mineral = False

                for mineral in item.z_reprocessed_items:
                    if mineral.id not in minidlookup:
                        continue

                    idx = minidlookup[mineral.id]
                    repro_qty = math.ceil(float(mineral.z_qty) * reprocess_pct)
                    mineral_value += float(mineral.sell_fivepct_price) * repro_qty
                    max_qty = max(max_qty, int(requirements[idx]) / int(repro_qty))

                    if requirements[idx] > 0:
                        has_mineral = True
                        break

                if not has_mineral:
                    continue

                item.z_index = idx
                items.append(item)
                idx = idx + 1

                item.z_mineral_value = mineral_value
                item.z_mineral_ratio = float(item.sell_fivepct_price) / mineral_value

                if item.item_group.name != 'Ice':
                    related_items = Item.objects.filter(item_group_id=item.item_group.id, name__iregex='^Compressed')
                    item.z_related_ids = [i.id for i in related_items]
                else:
                    item.z_related_ids = self.COMPRESSED_ICES[item.id]

                max_order_qty = item.get_max_order_volume(item_ids=item.z_related_ids)

                item.z_max_qty = min(max_qty, max_order_qty)

                # TODO: Properly calculate shipping?
                item.z_total_price = int(float(item.sell_fivepct_price) * 1.15 + float(item.volume * 290))

                item_maxes.append(item.z_max_qty)

        if allow_mineral_purchase:
            mineral_items = Item.objects.filter(id__in=mineralids)
            for item in mineral_items:
                minidx = minidlookup[item.id]
                item.z_index = idx
                idx = idx + 1
                item.z_mineral_value = item.sell_fivepct_price
                item.z_mineral_ratio = 1
                item.z_related_ids = [item.id]
                item.z_max_qty = requirements[minidx]

                item.z_total_price = int(float(item.sell_fivepct_price)* 1.15 + float(item.volume*290))

                item_maxes.append(item.z_max_qty)
                items.append(item)

        ttl_price_obj_fn = [i.z_total_price for i in items]
        base_price_obj_fn = [i.base_price for i in items]
        volume_obj_fn = [i.volume for i in items]

        if optimization_strategy == self.OPTIMIZATION_PRICE:
            obj_fns = [
                ttl_price_obj_fn,
                base_price_obj_fn,
                volume_obj_fn,
            ]
        else:
            obj_fns = [
                volume_obj_fn,
                ttl_price_obj_fn,
                base_price_obj_fn,
            ]

        for obj_fn in obj_fns:
            results = self.solve(obj_fn, mineralids, requirements, overage, items, item_maxes, source_station_ids=source_station_ids, dest_station_id=dest_station_id, reprocess_pct=reprocess_pct)

            if results is not None:
                all_items, total_price, fulfilled_all = results

                minerals = dict()
                full_mineral_value = 0
                for i in all_items:
                    for sid in i.z_orders:
                        order_list = i.z_orders[sid]
                        for o in order_list.orders:
                            for m in o.item.get_reprocessed_items():
                                if m.id not in minerals:
                                    minerals[m.id] = m
                                    m.z_ttl_value = 0
                                    m.z_fulfilled_qty = 0
                                mineral_qty = o.z_order_qty * Decimal(m.z_qty * reprocess_pct)
                                minerals[m.id].z_fulfilled_qty += mineral_qty
                                minerals[m.id].z_desired_qty = target_minerals[m.id] if m.id in target_minerals else 0
                                minerals[m.id].z_ttl_value += mineral_qty * m.sell_fivepct_price

                                full_mineral_value += mineral_qty * m.sell_fivepct_price

                mineral_value_ratio = total_price / full_mineral_value

                return all_items, fulfilled_all, mineral_value_ratio, minerals.values(), total_price
            else:
                print("No solution found...")

        return None

    def solve(self, obj_fn, mineralids, requirements, overage, items, item_maxes, timeout=10, source_station_ids=None, dest_station_id=None, reprocess_pct=0.875):
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
                        qty = math.floor(min.z_qty * reprocess_pct)  # Don't hard-code of course
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
                                min_qty[idx] += qty * sub.z_qty * reprocess_pct

            total_price = 0

            all_items = []

            fulfilled_all = True

            for item in items_to_buy:
                qty = item.z_qty_to_buy

                item.get_current_orders(qty, item_ids=item.z_related_ids, source_station_ids=source_station_ids, dest_station_id=dest_station_id)

                total_price += item.z_ttl_price_with_shipping

                if item.z_qty_remaining > 0:
                    fulfilled_all = False
                    print("Not fulfilled: %s, short: %d out of %d" % (item.item_group.name, item.z_qty_remaining, qty))

                all_items.append(item)

            return all_items, total_price, fulfilled_all

        return None


if __name__ == '__main__':
    # minerals = ['trit', 'pye', 'mex', 'iso', 'nocx', 'zyd', 'mega', 'morp']#, 'hw', 'stront', 'lo', 'hel', 'hyd', 'nit', 'oxy']
    mineralids = [34, 35, 36, 37, 38, 39, 40, 11399] #, 16272, 16275, 16273, 16274, 17889, 17888, 17887]
    requirements = [112254380, 27580450, 7008270, 1777650, 441840, 208280, 58110, 0] #, 0, 0, 0, 0, 0, 0, 0]
    overage = [0, 0, 0, 0, 0, 0, 0, 0]#, 0, 0, 0, 0, 0, 0, 0]

    target_minerals = dict([
        (34, 112254380),
        (35, 27580450),
        (36, 7008270),
        (37, 1777650),
        (38, 441840),
        (39, 208280),
        (40, 58110)
    ])

    target_minerals = dict([
        (17888, 4000000),
        (17889, 3000000),
        (17887, 3000000),
        (16274, 2000000),
    ])

    Calculator().calculate_optimal_ores(target_minerals=target_minerals, allow_mineral_purchase=True)

