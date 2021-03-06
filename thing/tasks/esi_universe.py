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

from django.db import transaction, connections

import traceback


class EsiUniverse(APITask):
    name = 'thing.esiuniverse'

    universe_types_url = 'https://esi.evetech.net/latest/universe/types?page=%s'
    universe_type_url = 'https://esi.evetech.net/latest/universe/types/%s'

    db = connections['default']

    bulk_query = '''INSERT INTO thing_item(id,name,item_group_id,market_group_id,portion_size,volume,packaged_volume,mass,description,icon_id,published,item_slot,lo_slots,med_slots,hi_slots,rig_slots,subsystem_slots,service_slots) 
VALUES %s 
ON DUPLICATE KEY UPDATE
    name=VALUES(name),
    item_group_id=VALUES(item_group_id),
    market_group_id=VALUES(market_group_id),
    portion_size=VALUES(portion_size),
    volume=VALUES(volume),
    packaged_volume=VALUES(packaged_volume),
    mass=VALUES(mass),
    description=VALUES(description),
    icon_id=VALUES(icon_id),
    published=VALUES(published),
    item_slot=VALUES(item_slot),
    lo_slots=VALUES(lo_slots),
    med_slots=VALUES(med_slots),
    hi_slots=VALUES(hi_slots),
    rig_slots=VALUES(rig_slots),
    subsystem_slots=VALUES(subsystem_slots),
    service_slots=VALUES(service_slots)
'''
    bulk_query_row = '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'

    def run(self):
        self.init()

        page = 1
        max_pages = None

        try:

            while max_pages is None or page <= max_pages:
                success, results, headers = self.fetch_esi_url(self.universe_types_url % str(page), None, headers_to_return=['x-pages'])
                    
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
                sql_params = []

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

                    if 'dogma_effects' in item:
                        slot = None
                        for e in item['dogma_effects']:
                            if e['effect_id'] == 11:
                                slot = 'loPower'
                            elif e['effect_id'] == 12:
                                slot = 'hiPower'
                            elif e['effect_id'] == 13:
                                slot = 'medPower'
                            elif e['effect_id'] == 2663:
                                slot = 'rigSlot'
                            elif e['effect_id'] == 3772:
                                slot = 'subSystem'
                            elif e['effect_id'] == 6306:
                                slot = 'serviceSlot'

                        db_item.item_slot = slot

                    if 'dogma_attributes' in item:
                        for a in item['dogma_attributes']:
                            aid = a['attribute_id']
                            av = a['value']
                            if aid == 12:
                                db_item.lo_slots = av
                            elif aid == 13:
                                db_item.med_slots = av
                            elif aid == 14:
                                db_item.hi_slots = av
                            elif aid == 1137 or aid == 1154:
                                db_item.rig_slots = av
                            elif aid == 1367:
                                db_item.subsystem_slots = av
                            elif aid == 2056:
                                db_item.service_slots = av

                    sql_inserts.append(self.bulk_query_row)
                    sql_params.extend([
                        db_item.id,
                        db_item.name,
                        db_item.item_group_id,
                        db_item.market_group_id,
                        db_item.portion_size,
                        db_item.volume,
                        db_item.packaged_volume,
                        db_item.mass,
                        db_item.description,
                        db_item.icon_id,
                        db_item.published,
                        db_item.item_slot,
                        db_item.lo_slots,
                        db_item.med_slots,
                        db_item.hi_slots,
                        db_item.rig_slots,
                        db_item.subsystem_slots,
                        db_item.service_slots
                    ])

                self.execute_query(sql_inserts, sql_params)
                sql_inserts = []
                sql_params = []


        except Exception, e:
            traceback.print_exc(e)
            return False

        return True

    @transaction.atomic
    def execute_query(self, sql_inserts, params):
        cursor = self.db.cursor()

        order_ct = len(sql_inserts)

        if order_ct == 0:
            return

        sql = ','.join(sql_inserts)

        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute(self.bulk_query % sql, params)
        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()