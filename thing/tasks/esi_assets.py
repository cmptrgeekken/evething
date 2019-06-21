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

from thing.models import CharacterApiScope, EsiAsset, MoonExtraction, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

from django.core.cache import cache

from django.db import transaction

import traceback


class EsiAssets(APITask):
    name = 'thing.esiassets'

    char_asset_url = 'https://esi.evetech.net/latest/characters/%s/assets/?datasource=tranquility&page='
    corp_asset_url = 'https://esi.evetech.net/latest/corporations/%s/assets/?datasource=tranquility&page='

    def run(self):
        self.init()

        char_asset_scopes = CharacterApiScope.objects.filter(scope='esi-assets.read_assets.v1')
        corp_asset_scopes = CharacterApiScope.objects.filter(scope='esi-assets.read_corporation_assets.v1')

        seen_corps = set()

        for scope in corp_asset_scopes:
            char = scope.character

            if 'Director' in char.get_apiroles():
                if char.corporation_id not in seen_corps\
                        and char.corporation_id is not None:
                    success = self.import_assets(char, True)
                    if not success:
                        continue
                    seen_corps.add(char.corporation_id)
                    if char.corporation.alliance_id is not None:
                        ihubs = dictfetchall(queries.ihub_upgrades % char.corporation.alliance_id)
                        cache.set('structure-ihubs-%d' % char.corporation.alliance_id, ihubs)

                        gates = dictfetchall(queries.jumpbridge_lo_quantity % char.corporation.alliance_id)
                        cache.set('structure-gates-%d' % char.corporation.alliance_id, gates)

                        cursor = self.get_cursor()
        cursor.execute(queries.jumpbridge_lo_history_update)

        #for scope in char_asset_scopes:
        #    self.import_assets(scope.character, False)

        #for scope in corp_asset_scopes:
        #    self.import_assets(scope.character, True)
        # EsiAsset.objects.rebuild()

    def import_assets(self, character, is_corporation):
        char_id = character.id
        corp_id = character.corporation.id

        page = 1
        max_pages = None

        start_time = datetime.datetime.now()
        try:

            cursor = self.get_cursor()

            cursor.execute('DROP TABLE IF EXISTS thing_esiasset_tmp;')
            cursor.execute('CREATE TABLE thing_esiasset_tmp LIKE thing_esiasset;')
            
            seen_ids = set()

            if is_corporation:
                api_url = self.corp_asset_url % corp_id
            else:
                api_url = self.char_asset_url % char_id

            initial_url = api_url + '1'

            #self.log_debug('Starting fetch at %s' % start_time)

            success, data, headers = self.fetch_esi_url(initial_url, character, headers_to_return=['x-pages', 'last-modified'])
            if not success:
                self.log_error('Failed to load assets for %d' % (char.corporation.name if is_corporation else char.name))
                return False

            max_pages = int(headers['x-pages']) if 'x-pages' in headers else 1

            urls = [api_url + str(i) for i in range(2, max_pages+1)]

            if max_pages > 1:
                all_asset_data = self.fetch_batch_esi_urls(urls, character, batch_size=20, headers_to_return=['last-modified'])
            else:
                all_asset_data = dict()
            
            all_asset_data[initial_url] = (success, data, headers)
            sql_inserts = []

            for url, asset_data in all_asset_data.items():
                success, results, headers = asset_data

                if not success:
                    self.log_warn('Failed to load results: %s' % results)
                    return False

                asset_info = json.loads(results)

                if len(asset_info) == 0:
                    self.log_warn('Received empty asset list for %s' % character.corporation.name)
                    if page != max_pages:
                        return False
                    break

                if 'last-modified' in headers:
                    last_updated = self.parse_esi_date(headers['last-modified'])
                else:
                    last_updated = datetime.datetime.now()

                for asset in asset_info:
		    type_id = int(asset['type_id'])
                    item_id = int(asset['item_id'])
                    location_id = int(asset['location_id'])
                    location_type = asset['location_type']
                    location_flag = asset['location_flag']
                    is_singleton = int(asset['is_singleton'])
                    if 'quantity' in asset:
                        quantity = int(asset['quantity'])
                    else:
                        quantity = 1

		    if 'is_blueprint_copy' in asset:
                        is_blueprint_copy = int(asset['is_blueprint_copy'])
                    else:
                        is_blueprint_copy = 0

                    if is_corporation:
                        corporation_id = corp_id
                        character_id = 'NULL'
                    else:
                        character_id = char_id
                        corporation_id = 'NULL'

                    if item_id in seen_ids:
                        continue

                    seen_ids.add(item_id)

		    new_sql = "(%s, %s, %s, %s, %s, %s, '%s', %s, '%s', %s, '%s')" \
				% (character_id, corporation_id, item_id, type_id, is_singleton, is_blueprint_copy, location_flag, location_id, location_type, quantity, last_updated)
                    sql_inserts.append(new_sql)
                
                if len(sql_inserts) >= 10000:
                    #self.log_debug('Inserting %d record...' % len(sql_inserts))
                    self.execute_query(cursor, sql_inserts)
                    sql_inserts = []

            self.execute_query(cursor, sql_inserts)
        except Exception, e:
            traceback.print_exc(e)
            return False

        if is_corporation:
            cursor.execute('SELECT COUNT(*) FROM thing_esiasset WHERE corporation_id = %d' % corp_id)
        else:
            cursor.execute('SELECT COUNT(*) FROM thing_esiasset WHERE character_id = %d' % char_id)
        
        row_ct = cursor.fetchone()[0]

        if row_ct > len(seen_ids) * 10:
            self.log_warn('More than 10%% of assets have failed to load. Cancelling update. (%s vs %s)' % (row_ct,len(seen_ids)))
            return False

        #self.log_debug('Deleting removed assets.')

        if is_corporation: 
            cursor.execute('DELETE FROM thing_esiasset WHERE corporation_id=%d AND NOT EXISTS (SELECT 1 FROM thing_esiasset_tmp eat WHERE eat.item_id=thing_esiasset.item_id)' % corp_id)
        else:
            cursor.execute('DELETE FROM thing_esiasset WHERE character_id=%d AND NOT EXISTS (SELECT 1 FROM thing_esiasset_tmp eat WHERE eat.item_id=thing_esiasset.item_id)' % char_id)

        #self.log_debug('Updating existing assets')
        cursor.execute('UPDATE thing_esiasset ea INNER JOIN thing_esiasset_tmp eat ON ea.item_id=eat.item_id SET ea.character_id=eat.character_id, ea.corporation_id=eat.corporation_id, ea.location_flag=eat.location_flag, ea.location_id=eat.location_id, ea.location_type=eat.location_type, ea.quantity=eat.quantity,ea.last_updated=eat.last_updated;')
        #self.log_debug('Inserting new assets.')
        
        cursor.execute('INSERT IGNORE INTO thing_esiasset(`character_id`, `corporation_id`, `item_id`, `type_id`, `is_singleton`, `is_blueprint_copy`, `location_flag`, `location_id`, `location_type`, `quantity`, `last_updated`) SELECT eat.character_id, eat.corporation_id, eat.item_id, eat.type_id, eat.is_singleton, eat.is_blueprint_copy, eat.location_flag, eat.location_id, eat.location_type, eat.quantity, eat.last_updated from thing_esiasset_tmp eat LEFT JOIN thing_esiasset ea ON eat.item_id=ea.item_id WHERE ea.item_id IS NULL;')

        cursor.close()

        #self.log_debug('Done after %d seconds' % (datetime.datetime.now()-start_time).total_seconds())

        return True

    @transaction.atomic
    def execute_query(self, cursor, sql_inserts):
        order_ct = len(sql_inserts)

        if order_ct == 0:
            return

        sql = ','.join(sql_inserts)

        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute(queries.bulk_assets_tmp_insert % sql)
        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()

