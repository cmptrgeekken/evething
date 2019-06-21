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

from thing.models import Stargate, System
from thing import queries
from thing.utils import dictfetchall

from decimal import *

from django.core.cache import cache

from django.db import transaction

import traceback


class EsiSystems(APITask):
    name = 'thing.esisystems'

    systems_url = 'https://esi.evetech.net/latest/universe/systems/'
    system_url = 'https://esi.evetech.net/latest/universe/systems/%s'

    stargate_url = 'https://esi.evetech.net/latest/universe/stargates/%s'

    def run(self):
        self.init()


        try:
            success, results = self.fetch_esi_url(self.systems_url, None)
                    
            if not success:
                self.log_warn('Failed to load results: %s' % results)
                return False

            system_ids = json.loads(results)

            if len(system_ids) == 0:
                self.log_warn('Received empty type list')
                return

            # Retrieve type details
            urls = [self.system_url % str(i) for i in system_ids]

            print('[%s] Fetching %d systems' % (datetime.datetime.utcnow(), len(urls)))

            all_data = self.fetch_batch_esi_urls(urls, None, batch_size=10)

            print('[%s] %d systems retrieved!' % (datetime.datetime.utcnow(), len(urls)))
            gate_ids = []

            for url, system_data in all_data.items():
                success, data = system_data

                if not success:
                    self.log_warn('API returned an error for url %s' % url)
                    continue

                try:
                    system = json.loads(data)
                except:
                    self.log_warn('Could not parse data %s' % data)
                    continue

                system_id = int(system['system_id'])

                if 'stargates' in system:
                    gate_ids += [id for id in system['stargates']]


            gate_urls = [self.stargate_url % str(i) for i in gate_ids]

            print('[%s] Fetching %d gates...' % (datetime.datetime.utcnow(), len(gate_urls)))

            all_gates = self.fetch_batch_esi_urls(gate_urls, None, batch_size=10)
            print('[%s] %d Gates retrieved!' % (datetime.datetime.utcnow(), len(gate_urls)))

            current_ids = set([int(g['id']) for g in dictfetchall('SELECT id FROM thing_stargate')])

            sql_inserts = []

            for url, gate_data in all_gates.items():
                success, entry = gate_data

                if not success:
                    self.log_warn('API returned an error for url %s' % url)
                    continue

                try:
                    gate = json.loads(entry)
                except:
                    self.log_warn('Could not parse data %s' % entry)
                    continue

                gate_id = int(gate['stargate_id'])

                if gate_id in current_ids:
                    continue


                sql_insert = '(%d,%d,\'%s\',%d,%d,%d,%f,%f,%f)' % (gate_id, 
                        int(gate['system_id']), 
                        gate['name'], 
                        int(gate['destination']['stargate_id']), 
                        int(gate['destination']['system_id']), 
                        int(gate['type_id']),
                        float(gate['position']['x']),
                        float(gate['position']['y']),
                        float(gate['position']['z'])
                        )

                sql_inserts.append(sql_insert)

	    cursor = self.get_cursor()
	    self.execute_query(cursor, sql_inserts) 

        except Exception, e:
            traceback.print_exc(e)
            return False

        return True

    @transaction.atomic
    def execute_query(self, cursor, sql_inserts):
        order_ct = len(sql_inserts)

        if order_ct == 0:
            return

        sql = ','.join(sql_inserts)

	print('[%s] Inserting %d records!' % (datetime.datetime.utcnow(), len(sql_inserts)))

        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute('INSERT IGNORE INTO thing_stargate(id, system_id, name, destination_stargate_id, destination_system_id, type_id, x, y, z) VALUES %s' % sql)
        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()

