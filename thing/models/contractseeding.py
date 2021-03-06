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
from thing.models.station import Station
from thing.models.corporation import Corporation
from thing.models.character import Character
from thing.models.contract import Contract
from thing.models.contractitem import ContractItem
from thing.utils import dictfetchall
from thing import queries

import datetime

from django.core.cache import cache

import math

class ContractSeeding(models.Model):
    PRIORITIES = ['Low', 'Medium', 'High']

    id = models.AutoField(primary_key=True)
    char = models.ForeignKey(Character, on_delete=models.DO_NOTHING, db_column='char_id')
    corp = models.ForeignKey(Corporation, on_delete=models.DO_NOTHING)
    station = models.ForeignKey(Station, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=4000)
    min_qty = models.IntegerField()
    is_private = models.BooleanField(default=True)
    raw_text = models.TextField()
    estd_price = models.DecimalField(max_digits=20, decimal_places=2)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    current_qty = models.IntegerField(default=0)
    last_modified = models.DateTimeField(default=datetime.datetime.now)
    qty_last_modified = models.DateTimeField(default=None)
    last_modified_by = models.ForeignKey(Character, on_delete=models.DO_NOTHING, db_column='last_modified_by', related_name='last_modified_by')
    alliance_qty = models.IntegerField(default=0)
    corp_qty = models.IntegerField(default=0)

    stock_count = None
    seed_price = None

    def get_items(self):
        from thing.models.contractseedingitem import ContractSeedingItem

        return ContractSeedingItem.objects.filter(contractseeding_id=self.id).order_by('-required', 'item__name')

    def get_estd_price(self):
        estd_price = 0
        for i in self.get_items():
            i.item.get_current_orders(quantity=i.min_qty, ignore_seed_items=False, dest_station_id=self.station_id, source_station_ids=[60003760])
            if i.item.item_group.category.name == 'Ship':
                estd_price += i.item.z_ttl_price_multibuy
            else:
                estd_price += i.item.z_ttl_price_with_shipping
        return estd_price


    def get_stock(self, page=1, page_size=20):

        contracts = dictfetchall(queries.contractseeding_contracts % self.id)
        contract_ids = []
        for c in contracts:
            contract_ids.append(c['contract_id'])

        contracts = Contract.objects.filter(contract_id__in=contract_ids).order_by('price')
        contracts_trimmed = dict()
        for c in contracts:
            contracts_trimmed[c.contract_id] = c

        contracts = contracts_trimmed.values()
            
        ttl_pages = int(math.ceil(len(contracts) / float(page_size))) + 1


        if page is not None:
            return contracts[page_size*(page-1):page_size*page], ttl_pages
        else:
            return contracts

    def get_priority(self):
        return self.PRIORITIES[self.priority]

    def get_stock_count(self):
        if self.stock_count is None:
            self.stock_count = len(self.get_stock(page=None))
        return self.stock_count

    def get_corp_stock(self):
        stock = self.get_stock(page=None)
        ct = 0
        for s in stock:
            if s.assignee_id == 98388312:
                ct+=1
        return ct

    def get_alliance_stock(self):
        stock = self.get_stock(page=None)
        ct = 0
        for s in stock:
            if s.assignee_id == 99005338:
                ct+=1
        return ct

    def get_seed_price(self):
        if self.seed_price is not None:
            return self.seed_price

        self.seed_price = 0
        for item in self.get_items():
            item.item.get_current_orders(quantity=item.min_qty)

            self.seed_price += item.item.z_ttl_price_multibuy

        return self.seed_price

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name

