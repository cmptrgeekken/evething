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

from thing.models import CharacterApiScope, EsiAsset, MoonExtraction, Item, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

from django.core.cache import cache

from django.db import transaction

import traceback


class EsiJournal(APITask):
    name = 'thing.esijournal'

    corp_journal_url = 'https://esi.evetech.net/latest/corporations/%s/wallets/%d/journal/?datasource=tranquility&page='


    def run(self):
        self.init()

        corp_asset_scopes = CharacterApiScope.objects.filter(scope='esi-wallet.read_corporation_wallets.v1')

        seen_corps = set()

        for scope in corp_asset_scopes:
            char = scope.character

            if 'Director' in char.get_apiroles():
                if char.corporation_id not in seen_corps\
                        and char.corporation_id is not None:
                    success = self.import_journal(char)
                    if not success:
                        continue
                    seen_corps.add(char.corporation_id)


    def import_journal(self, character):
        char_id = character.id
        corp_id = character.corporation.id

        page = 1
        max_pages = None

        start_time = datetime.datetime.now()
        try:

            cursor = self.get_cursor()

            for wallet_id in range(1, 8):
                api_url = self.corp_journal_url % (corp_id, wallet_id)

                initial_url = api_url + '1'

                #self.log_debug('Starting fetch at %s' % start_time)

                success, data, headers = self.fetch_esi_url(initial_url, character, headers_to_return=['x-pages', 'last-modified'])
                if not success:
                    self.log_error('Failed to load journal for %s via %s' % (char.corporation.name, char.name))
                    return False

                max_pages = int(headers['x-pages']) if 'x-pages' in headers else 1

                urls = [api_url + str(i) for i in range(2, max_pages+1)]

	        cursor.execute('SELECT MAX(`date`) FROM thing_esijournal WHERE corporation_id = %d AND wallet_id = %d' % (corp_id, wallet_id))

        	max_dt = cursor.fetchone()[0]


                if max_pages > 1:
                    all_journal_data = self.fetch_batch_esi_urls(urls, character, batch_size=20, headers_to_return=['last-modified'])
                else:
                    all_journal_data = dict()
            
                all_journal_data[initial_url] = (success, data, headers)
                sql_inserts = []
                sql_params = []

                for url, journal_data in all_journal_data.items():
                    success, results, headers = journal_data

                    if not success:
                        self.log_warn('Failed to load results: %s (%s %s %s)' % (results, url, character.name, character.corporation.name))
                        continue

                    journal_info = json.loads(results)

                    if len(journal_info) == 0:
                        if page != max_pages:
                            return False
                        break

                    for journal in journal_info:
                        journal_id = int(journal['id'])
                        amount = journal['amount']
                        balance = journal['balance']
                        context_id = int(journal['context_id']) if 'context_id' in journal else None
                        context_id_type = journal['context_id_type'] if 'context_id_type' in journal else None
                        date = self.parse_api_date(journal['date'], True)
                        description = journal['description']
                        first_party_id = int(journal['first_party_id'])
                        reason = journal['reason'] if 'reason' in journal else None
                        ref_type = journal['ref_type']
                        second_party_id = int(journal['second_party_id'])

			if max_dt is not None and date < max_dt:
                            continue

                        new_sql = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

                        sql_inserts.append(new_sql)
                        sql_params.extend([journal_id, amount, balance, context_id, context_id_type, date, description, first_party_id, reason, ref_type, second_party_id, corp_id, wallet_id])
                
                        if len(sql_inserts) >= 1000:
                            #self.log_debug('Inserting %d record...' % len(sql_inserts))
                            self.execute_query(cursor, sql_inserts, sql_params)
                            sql_inserts = []
                            sql_params = []
                if len(sql_inserts) > 0:
                    self.execute_query(cursor, sql_inserts, sql_params)

            cursor.execute("INSERT INTO thing_character(id,name) SELECT DISTINCT first_party_id, '*UNKNOWN*' FROM thing_esijournal ej LEFT JOIN thing_character ch ON ej.first_party_id=ch.id WHERE ej.ref_type in ('structure_gate_jump','bounty_prize','industry_job_tax','planetary_import_tax','planetary_export_tax') AND ch.id is null;")
        except Exception, e:
            traceback.print_exc(e)
            return False

        cursor.close()

        #self.log_debug('Done after %d seconds' % (datetime.datetime.now()-start_time).total_seconds())

        return True

    @transaction.atomic
    def execute_query(self, cursor, sql_inserts, sql_params):
        order_ct = len(sql_inserts)

        if order_ct == 0:
            return

        sql = ','.join(sql_inserts)
        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute(queries.bulk_journal_insert % sql, sql_params)

        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()

