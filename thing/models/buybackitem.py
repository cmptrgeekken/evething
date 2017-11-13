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
from thing.models.item import Item
from thing.models.itemcategory import ItemCategory
from thing.models.itemgroup import ItemGroup
from thing.models.buybackprogram import BuybackProgram


class BuybackItem(models.Model):
    id = models.IntegerField(primary_key=True)
    buyback = models.ForeignKey(BuybackProgram, on_delete=models.DO_NOTHING)
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING, null=True)
    group = models.ForeignKey(ItemGroup, on_delete=models.DO_NOTHING, null=True)
    category = models.ForeignKey(ItemCategory, on_delete=models.DO_NOTHING, null=True)
    price_type = models.CharField(max_length=8, default='5day')
    price_pct = models.FloatField(default=1)
    reprocess = models.BooleanField(default=False)
    active = models.BooleanField(default=False)

    price_region_id = 10000002

    def get_price(self, reprocess=None, issued=None, pct=None):
        if reprocess is None:
            reprocess = self.reprocess

        if pct is None:
            pct = self.price_pct

        if self.price_type == '5day':
            return self.item.get_history_avg(days=5, region_id=self.price_region_id, issued=issued,
                                             pct=pct, reprocess=reprocess)
        return 0

    def get_buyback_type(self):
        type_str = ''
        if self.price_type == '5day':
            type_str = '%0.0f%% of 5-day Jita Average' % (self.price_pct * 100.0)

        if self.reprocess:
            type_str += ' of max-reprocessed materials'

        return type_str

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.item.name
