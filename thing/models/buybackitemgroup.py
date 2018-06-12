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

from thing.models.buyback import Buyback
from thing.models.buybacklocationgroup import BuybackLocationGroup


class BuybackItemGroup(models.Model):
    id = models.IntegerField(primary_key=True)
    buyback = models.ForeignKey(Buyback, on_delete=models.DO_NOTHING)
    buyback_location_group = models.ForeignKey(BuybackLocationGroup, on_delete=models.DO_NOTHING)

    name = models.CharField(max_length=100)

    price_type = models.CharField(max_length=8, default='5day')
    price_pct = models.FloatField(default=1)
    reprocess = models.BooleanField(default=False)
    reprocess_pct = models.FloatField(default=.876)
    reprocess_tax = models.FloatField(default=0)

    active = models.BooleanField(default=False)

    class BuybackItemGroupEntry:

        price_region_id = 10000002

        def __init__(self, item, buybackitem, buybackitemgroup):
            self.item = item

            self.price_type = buybackitem.price_type or buybackitemgroup.price_type
            self.price_pct = buybackitem.price_pct or buybackitemgroup.price_pct
            self.reprocess = buybackitem.reprocess or buybackitemgroup.reprocess
            self.reprocess_pct = buybackitem.reprocess_pct or buybackitemgroup.reprocess_pct

            if buybackitem.reprocess_tax is not None:
                self.reprocess_tax = buybackitem.reprocess_tax
            else:
                self.reprocess_tax = buybackitemgroup.reprocess_tax or 0.0

        def get_price(self, reprocess=None, issued=None, pct=None):
            if reprocess is None:
                reprocess = self.reprocess

            if pct is None:
                pct = self.price_pct

            item_price = 0

            if self.price_type == '5day':
                item_price = self.item.get_history_avg(days=5, region_id=self.price_region_id, issued=issued,
                                                 pct=pct, reprocess=reprocess, reprocess_pct=self.reprocess_pct)
            elif self.price_type == 'buy':
                item_price = self.price_pct*self.item.get_price(True, reprocess=reprocess, reprocess_pct=self.reprocess_pct)

            if self.reprocess_tax is not None:
                item_price *= (1-self.reprocess_tax)

            return round(item_price, 2)

        def get_buyback_type(self):
            type_str = ''
            if self.price_type == '5day':
                type_str = '%0.0f%% of 5-day Jita Average' % (self.price_pct * 100.0)
            elif self.price_type == 'buy':
                type_str = '%0.0f%% of Jita Buy' % (self.price_pct * 100)

            if self.reprocess:
                type_str += '<br/>@ %0.1f%% refine' % (self.reprocess_pct*100.0)

            if self.reprocess_tax > 0:
                type_str += '<br/>(minus %0.0f%% tax)' % (self.reprocess_tax*100.0)

            return type_str

    def get_items(self):
        from thing.models import BuybackItem

        # First grab accepted items.
        # Ordering by market ensures that market group entries are first and item groups
        accepted_items = BuybackItem.objects.filter(buyback_item_group_id=self.id, active=True, accepted=True).order_by('-market_group_id')

        items = dict()

        for ai in accepted_items:
            for i in ai.get_items():
                items[i.id] = self.BuybackItemGroupEntry(i, ai, self)

        # Then delete rejected items
        rejected_items = BuybackItem.objects.filter(buyback_item_group_id=self.id, active=True, accepted=False)
        for ri in rejected_items:
            for i in ri.get_items():
                del items[i.id]

        all_items = items.values()

        all_items.sort(key=lambda i: i.item.name)

        return all_items

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name
