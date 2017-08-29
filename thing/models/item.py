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

from decimal import Decimal

from django.db import models
from django.db.models import Sum, F

from thing.models.itemgroup import ItemGroup
from thing.models.marketgroup import MarketGroup
from thing import queries

class Item(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    item_group = models.ForeignKey(ItemGroup, on_delete=models.DO_NOTHING)
    market_group = models.ForeignKey(MarketGroup, blank=True, null=True, on_delete=models.DO_NOTHING)

    portion_size = models.IntegerField()
    # 0.0025 -> 10,000,000,000
    volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    base_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    sell_fivepct_price = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sell_fivepct_volume = models.IntegerField(default=0)

    sell_avg_price = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sell_total_volume = models.IntegerField(default=0)

    buy_fivepct_price = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    buy_fivepct_volume = models.IntegerField(default=0)

    buy_avg_price = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    buy_total_volume = models.IntegerField(default=0)

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name

    def icon(self, w=32):
        return "https://imageserver.eveonline.com/InventoryType/%d_%d.png" % (self.id, w)

    def get_reprocessed_items(self):
        from itemmaterial import ItemMaterial

        materials = ItemMaterial.objects.filter(
            item_id=self.id,
        ).select_related('item_material')

        items = []

        for material in materials:
            item = material.material
            item.z_qty = material.quantity

            items.append(item)

        return items

    def get_max_order_volume(self, buy=False, item_ids=None, station_ids=None):
        from thing.models.stationorder import StationOrder

        if item_ids is None:
            item_ids = [self.id]

        orders = StationOrder.objects.filter(item_id__in=item_ids, buy_order=buy)

        if station_ids is not None:
            orders = orders.filter(station_id__in=station_ids)

        return orders.aggregate(total_volume=Sum('volume_remaining'))['total_volume']

    def get_current_orders(self, quantity,
                           buy=False,
                           ignore_seed_items=True,
                           source_station_ids=None,
                           dest_station_id=1021577519493,
                           item_ids=None,
                           scale_by_repro=True,
                           buy_tolerance=.02):
        from thing.models.itemstationseed import ItemStationSeed
        from thing.models.stationorder import StationOrder

        if item_ids is None:
            item_ids = [self.id]

        orders = StationOrder.objects.filter(item_id__in=item_ids)

        if ignore_seed_items:
            seed_items = ItemStationSeed.objects.all()

            for seed_item in seed_items:
                orders = orders.exclude(item_id=seed_item.item_id, station_id=seed_item.station_id)

        if source_station_ids is not None:
            orders = orders.filter(station_id__in=source_station_ids)

        orders = orders.select_related('item')

        item_id_lookup = ','.join([str(i) for i in item_ids])

        shipping_query = queries.order_calculateshipping % ('price', 'item_id', 'thing_stationorder.station_id', str(dest_station_id))

        # TODO: Move Shipping Calculation to separate table
        orders = orders.extra(select={
            'price_with_shipping': 'price + (%s)' % shipping_query,
            'scaled_price_with_shipping': '''
SELECT price * SUM(im.quantity) / 
    (SELECT SUM(im2.quantity)
    FROM thing_itemmaterial im2  
    WHERE im2.item_id IN(%s)
    GROUP BY im2.id
    ORDER BY SUM(im2.quantity)
    LIMIT 1) + (%s)
    FROM thing_itemmaterial im WHERE im.item_id=thing_stationorder.item_id
            ''' % (item_id_lookup, shipping_query),
            'shipping': shipping_query
        })

        orders = orders.filter(buy_order=buy)

        if scale_by_repro and len(item_ids) > 1:
            orders = orders.order_by('scaled_price_with_shipping')
        else:
            orders = orders.order_by('price_with_shipping')

        qty_remaining = quantity

        orders_list = []

        ttl_price_best = 0
        ttl_price_multibuy = 0
        ttl_shipping = 0
        ttl_price_plus_shipping = 0

        last_updated = None

        stations = {}
        for order in orders:
            if order.price_with_shipping is None:
                continue

            order_qty = min(qty_remaining, order.volume_remaining)

            qty_remaining = max(0, qty_remaining-order_qty)
            ttl_price_best += order_qty * float(order.price)

            order.z_order_qty = order_qty
            order.z_price_with_shipping = round(order.price_with_shipping*100)/100

            order.z_shipping = round(order.shipping*100)/100

            orders_list.append(order)

            last_updated = order.last_updated if last_updated is None else max(last_updated, order.last_updated)

            if order_qty > 0:
                if order.station_id not in stations:
                    stations[order.station_id] = 0
                stations[order.station_id] += 1

                ttl_shipping += order.z_shipping*order_qty
                ttl_price_plus_shipping += order.z_price_with_shipping*order_qty

                ttl_price_multibuy = (quantity - qty_remaining) * float(order.price)

        self.z_qty_remaining = qty_remaining
        self.z_qty = quantity - qty_remaining
        self.z_ttl_price_best = ttl_price_best
        self.z_ttl_price_multibuy = ttl_price_multibuy
        self.z_orders = orders_list
        self.z_last_updated = last_updated
        self.z_ttl_volume = float(self.volume) * self.z_qty
        self.z_ttl_shipping = ttl_shipping
        self.z_ttl_price_plus_shipping = ttl_price_plus_shipping
        self.z_multibuy_test = float(ttl_price_best) < float(ttl_price_multibuy) * (1-buy_tolerance)
        self.z_station_count = len(stations)
        self.z_last_updated = last_updated

        return orders_list, ttl_price_best, ttl_price_multibuy, last_updated, qty_remaining, len(stations)

    def get_history_avg(self, days=5, region_id=10000002, issued=None, pct=1.0, reprocess=False):
        from thing.models.pricehistory import PriceHistory

        average = 0

        if reprocess:
            materials = self.get_reprocessed_items()
            for material in materials:
                # TODO: Calculate reprocessing rate correctly
                average += material.z_qty * .875 * material.get_history_avg(days=days, region_id=region_id, issued=issued, pct=pct, reprocess=False)

            return average

        query = PriceHistory.objects.filter(
            item_id=self.id,
            region_id=region_id
        ).order_by('-date')

        if issued is not None:
            query = query.filter(
                date__lte=issued
            )

        results = query.all()[:days].aggregate(
            total_value=Sum('average', field='average*movement'),
            total_volume=Sum('movement')
        )

        if results['total_value'] is None:
            return 0

        average = round(float(results['total_value'] / results['total_volume']) * pct, 2)

        return average

    def get_volume(self, days=7):
        iph_days = self.pricehistory_set.all()[:days]
        agg = self.pricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
        if agg['movement__sum'] is None:
            return Decimal('0')
        else:
            return Decimal(str(agg['movement__sum']))
