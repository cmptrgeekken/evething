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

import datetime
import time

from decimal import Decimal

from .apitask import APITask
import json

from thing.models import Alliance, Character, CharacterApiScope, Contract, ContractItem, ContractSeeding, Corporation, Event, Item, Station, APIKey, UserProfile
from django.db.models import Q

from multiprocessing import Pool, Value, Array


class EsiContractSeeding(APITask):
    name = 'thing.esi_contractseeding'

    def run(self):
        self.init()
        
        self.update_seeding()

    def update_seeding(self):
        seed_item_ids = ContractSeeding.objects.filter(is_active=True).values_list('id', flat=True)

        print('Updating %d contract seed items...' % len(seed_item_ids))

        for item_id in seed_item_ids:
            item = ContractSeeding.objects.get(id=item_id)
            if item is None:
                continue

            current_qty = item.get_stock_count()
            corp_qty = item.get_corp_stock()
            alliance_qty = item.get_alliance_stock()
            qty_last_modified = datetime.datetime.now()
            estd_price = item.get_estd_price()

            item = ContractSeeding.objects.get(id=item_id)
            if item is None:
                continue

            item.current_qty = current_qty
            item.corp_qty = corp_qty
            item.alliance_qty = alliance_qty
            item.qty_last_modified = qty_last_modified
            item.estd_price = estd_price

            item.save()


