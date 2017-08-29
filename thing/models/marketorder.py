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

from django.db import models

from thing.models.character import Character
from thing.models.corpwallet import CorpWallet
from thing.models.item import Item
from thing.models.station import Station


class MarketOrder(models.Model):
    """Market orders"""
    order_id = models.BigIntegerField(primary_key=True)

    station = models.ForeignKey(Station, on_delete=models.DO_NOTHING)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    character = models.ForeignKey(Character, on_delete=models.DO_NOTHING)
    corp_wallet = models.ForeignKey(CorpWallet, null=True, blank=True, on_delete=models.DO_NOTHING)

    creator_character_id = models.IntegerField(db_index=True)

    escrow = models.DecimalField(max_digits=14, decimal_places=2)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=17, decimal_places=2)

    buy_order = models.BooleanField(default=False)
    volume_entered = models.IntegerField()
    volume_remaining = models.IntegerField()
    minimum_volume = models.IntegerField()
    issued = models.DateTimeField(db_index=True)
    expires = models.DateTimeField(db_index=True)

    def check_undercut(self):
        from thing.models.stationorder import StationOrder

        owned_orders_query = MarketOrder.objects.filter(creator_character_id=self.creator_character_id)
        owned_order_ids = [o.order_id for o in owned_orders_query]

        orders_query = StationOrder.objects.filter(
            item_id=self.item.id,
            buy_order=self.buy_order,
            ).exclude(order_id__in=owned_order_ids)

        if self.buy_order:
            next_order_info = orders_query.filter(price__gte=self.price, station__system__constellation__region_id=self.station.system.constellation.region_id).aggregate(price=models.Max('price'), volume=models.Sum('volume_remaining'))
            next_order_price = next_order_info['price']
            next_order_volume = next_order_info['volume']

        else:
            next_order_info = orders_query.filter(price__lte=self.price, station_id=self.station.id).aggregate(price=models.Min('price'), volume=models.Sum('volume_remaining'))
            next_order_price = next_order_info['price']
            next_order_volume = next_order_info['volume']



        if next_order_price is not None\
                and next_order_price > 0:
            outbid = True
            outbid_price = next_order_price
            outbid_volume = next_order_volume
        else:
            outbid = False
            outbid_price = 0
            outbid_volume = 0

        return outbid, outbid_price, outbid_volume

    class Meta:
        app_label = 'thing'
        ordering = ('buy_order', 'item__name')
