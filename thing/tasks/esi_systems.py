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

from thing.models import Region, Constellation, Stargate, System
from thing import queries
from thing.utils import dictfetchall

from decimal import *

from django.core.cache import cache

from django.db import transaction

import traceback


class EsiSystems(APITask):
    name = 'thing.esisystems'

    regions_url = 'https://esi.evetech.net/latest/universe/regions/'
    region_url = 'https://esi.evetech.net/latest/universe/regions/%s'

    constellations_url = 'https://esi.evetech.net/latest/universe/constellations/'
    constellation_url = 'https://esi.evetech.net/latest/universe/constellations/%s'

    systems_url = 'https://esi.evetech.net/latest/universe/systems/'
    system_url = 'https://esi.evetech.net/latest/universe/systems/%s'

    stargate_url = 'https://esi.evetech.net/latest/universe/stargates/%s'

    def run(self):
        self.init()

        self.import_regions()
        self.import_constellations()
        self.import_gates()

    def import_regions(self):
        try:
            success, results = self.fetch_esi_url(self.regions_url, None)

            if not success:
                self.log_warn('Failed to load regions: %s' % results)

            existing_ids = set(Region.objects.values_list('id', flat=True))

            region_ids = json.loads(results)

            missing_regions = dict()

            region_constellations = dict()

            if len(region_ids) == 0:
                self.log_warn('Received empty type list')
                return False
            urls = [self.region_url % str(i) for i in region_ids]

            print('[%s] Fetching %d regions' % (datetime.datetime.utcnow(), len(urls)))

            all_data = self.fetch_batch_esi_urls(urls, None, batch_size=10)
            
            for url, region_data in all_data.items():
                success, data = region_data

                if not success:
                    self.log_warn('API returned an error for url %s' % url)
                    continue

                region = json.loads(data)

                region_id = region['region_id']

                db_region = Region()
                db_region.id = region_id
                db_region.name = region['name']
                db_region.save()

                region_constellations[region_id] = region['constellations']

        except Exception, e:
            traceback.print_exc(e)
            return False

        return region_constellations

    def import_constellations(self):
        try:
            success, results = self.fetch_esi_url(self.constellations_url, None)

            if not success:
                self.log_warn('Failed to load constellations: %s' % results)

            existing_ids = set(Constellation.objects.values_list('id', flat=True))

            constellation_ids = json.loads(results)

            missing_constellations = dict()

            constellation_constellations = dict()

            if len(constellation_ids) == 0:
                self.log_warn('Received empty type list')
                return False
            urls = [self.constellation_url % str(i) for i in constellation_ids]

            print('[%s] Fetching %d constellations' % (datetime.datetime.utcnow(), len(urls)))

            all_data = self.fetch_batch_esi_urls(urls, None, batch_size=10)
            
            for url, constellation_data in all_data.items():
                success, data = constellation_data

                if not success:
                    self.log_warn('API returned an error for url %s' % url)
                    continue

                constellation = json.loads(data)

                constellation_id = constellation['constellation_id']

                db_constellation = Constellation()
                db_constellation.id = constellation_id
                db_constellation.region_id = constellation['region_id']
                db_constellation.name = constellation['name']
                db_constellation.save()

                # constellation_constellations[constellation_id] = constellation['constellations']

        except Exception, e:
            traceback.print_exc(e)
            return False

        return constellation_constellations


    def import_gates(self):
        current_gates = dictfetchall('SELECT id, system_id FROM thing_stargate')


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

            gates_to_delete = set(Stargate.objects.values_list('id', flat=True))

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

                db_system = System.objects.filter(id=system_id).first()
                if db_system is None:
                    db_system = System()
                    db_system.id = system_id
                db_system.name = system['name']
                db_system.constellation_id = system['constellation_id']
                db_system.save()

                if 'stargates' in system:
                    for id in system['stargates']:
                        if id in gates_to_delete:
                            gates_to_delete.remove(id)
                        gate_ids.append(id)

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

            if len(gates_to_delete) > 0:
                print('[%s] Deleting %d gates' % (datetime.datetime.utcnow(), len(gates_to_delete)))

                Stargate.objects.filter(id__in=gates_to_delete).delete()

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

