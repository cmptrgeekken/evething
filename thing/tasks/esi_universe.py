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

from .apitask import APITask
import json

from thing.models import Item
from thing import queries
from thing.utils import dictfetchall

from decimal import *

from django.core.cache import cache

from django.db import transaction

import traceback


class EsiUniverse(APITask):
    name = 'thing.esiuniverse'

    universe_types_url = 'https://esi.evetech.net/latest/universe/types'
    universe_type_url = 'https://esi.evetech.net/latest/universe/types/%s'

    def run(self):
        self.init()

        page = 1
        max_pages = None

        try:

            while max_pages is None or page <= max_pages:
                success, results, headers = self.fetch_esi_url(self.universe_types_url, None, headers_to_return=['x-pages'])
                    
                if not success:
                    self.log_warn('Failed to load results: %s' % results)
                    return False

                max_pages = int(headers['x-pages']) if 'x-pages' in headers else 1
                page += 1
                type_ids = json.loads(results)

                if len(type_ids) == 0:
                    self.log_warn('Received empty type list')
                    if page != max_pages:
                        return False
                    break

                # Retrieve type details
                urls = [self.universe_type_url % str(i) for i in type_ids]

                all_data = self.fetch_batch_esi_urls(urls, None, batch_size=10)
                sql_inserts = []

                for url, type_data in all_data.items():
                    success, data = type_data

                    if not success:
                        self.log_warn('API returned an error for url %s' % url)
                        continue

                    try:
                        item = json.loads(data)
                    except:
                        self.log_warn('Could not parse data %s' % data)
                        continue

                    item_id = int(item['type_id'])
                    db_item = Item.objects.filter(id=item['type_id']).first()

                    if db_item is None:
                        db_item = Item()
                        db_item.id=item_id

                    db_item.name = item['name']
                    db_item.item_group_id = int(item['group_id']) if 'group_id' in item else None
                    db_item.market_group_id = int(item['market_group_id']) if 'market_group_id' in item else None
                    db_item.portion_size = int(item['portion_size']) if 'portion_size' in item else None
                    db_item.volume = Decimal(item['volume']) if 'volume' in item else None
                    db_item.packaged_volume = Decimal(item['packaged_volume']) if 'packaged_volume' in item else None
                    db_item.mass = float(item['mass']) if 'mass' in item else None
                    db_item.description = item['description']
                    db_item.icon_id = int(item['icon_id']) if 'icon_id' in item else None
                    db_item.published = bool(item['published'])

                    try:

                        db_item.save()
                    except Exception, e:
                        print(data)
                        traceback.print_exc(e)
                        return False


        except Exception, e:
            traceback.print_exc(e)
            return False

        return True
