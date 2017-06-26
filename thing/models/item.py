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


class Item(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    item_group = models.ForeignKey(ItemGroup)
    market_group = models.ForeignKey(MarketGroup, blank=True, null=True)

    portion_size = models.IntegerField()
    # 0.0025 -> 10,000,000,000
    volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    base_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_volume = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    sell_std_dev = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_median = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_percentile = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    buy_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_volume = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    buy_std_dev = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_median = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_percentile = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name

    def icon(self, w=32):
        return "https://imageserver.eveonline.com/InventoryType/%d_%d.png" % (self.id, w)

    def get_current_orders(self, quantity, buy=False, ignored_stations=None):
        from thing.models.itemstationseed import ItemStationSeed
        from thing.models.stationorder import StationOrder

        orders = StationOrder.objects.filter(item_id=self.id)

        seed_items = ItemStationSeed.objects.all()

        for seed_item in seed_items:
            orders = orders.exclude(item_id=seed_item.item_id, station_id=seed_item.station_id)

        if ignored_stations is not None:
            orders = orders.exclude(station_id__in=ignored_stations)

        orders = orders.select_related('item')

        # TODO: Move Shipping Calculation to separate table
        orders = orders.extra(select={
            'price_with_shipping': 'CASE WHEN station_id = 60003760 THEN price*1.015 + volume*390 ELSE price END',
            'shipping': 'CASE WHEN station_id = 60003760 THEN price*0.015 + volume*390 ELSE 0 END'
        })

        orders = orders.filter(buy_order=buy)

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
            order_qty = min(qty_remaining, order.volume_remaining)

            qty_remaining = max(0, qty_remaining-order_qty)
            ttl_price_best += order_qty * order.price

            order.z_order_qty = order_qty
            order.z_price_with_shipping = round(order.price_with_shipping*100)/100
            order.z_shipping = round(order.shipping*100)/100

            orders_list.append(order)

            last_updated = order.last_updated if last_updated is None else max(last_updated, order.last_updated)

            if order.station_id not in stations:
                stations[order.station_id] = 0
            stations[order.station_id] += 1

            ttl_shipping += order.z_shipping*order_qty
            ttl_price_plus_shipping += order.z_price_with_shipping*order_qty

            ttl_price_multibuy = quantity * order.price
            if qty_remaining <= 0:
                break

        self.z_qty_remaining = qty_remaining
        self.z_qty = quantity - qty_remaining
        self.z_ttl_price_best = ttl_price_best
        self.z_ttl_price_multibuy = ttl_price_multibuy
        self.z_orders = orders_list
        self.z_last_updated = last_updated
        self.z_ttl_volume = self.volume * self.z_qty
        self.z_ttl_shipping = ttl_shipping
        self.z_ttl_price_plus_shipping = ttl_price_plus_shipping
        self.z_multibuy_test = float(ttl_price_best) < float(ttl_price_multibuy) * 0.98
        self.z_station_count = len(stations)
        self.z_last_updated = last_updated

        return orders_list, ttl_price_best, ttl_price_multibuy, last_updated, qty_remaining, len(stations)

    def get_history_avg(self, days=5, region_id=10000002, issued=None, pct=1.0):
        from thing.models.pricehistory import PriceHistory

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

        return round(float(results['total_value'] / results['total_volume']) * pct, 2)

    def get_volume(self, days=7):
        iph_days = self.pricehistory_set.all()[:days]
        agg = self.pricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
        if agg['movement__sum'] is None:
            return Decimal('0')
        else:
            return Decimal(str(agg['movement__sum']))
