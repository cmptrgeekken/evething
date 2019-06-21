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

from thing.models.buybackitemgroup import BuybackItemGroup
from thing.models.item import Item
from thing.models.marketgroup import MarketGroup


class BuybackItem(models.Model):
    id = models.IntegerField(primary_key=True)
    buyback_item_group = models.ForeignKey(BuybackItemGroup, on_delete=models.DO_NOTHING)

    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    market_group = models.ForeignKey(MarketGroup, on_delete=models.DO_NOTHING)

    price_type = models.CharField(max_length=8, default='5day')
    price_pct = models.FloatField(default=1)
    repro_price_pct = models.FloatField(default=None)
    reprocess = models.BooleanField(default=False)
    reprocess_pct = models.FloatField(default=.876)
    reprocess_tax = models.FloatField(default=0)

    accepted = models.BooleanField(default=True)

    active = models.BooleanField(default=False)

    price_region_id = 10000002

    def get_items(self):
        if self.item is not None:
            return [self.item]

        return self.market_group.get_all_items()

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.item.name
