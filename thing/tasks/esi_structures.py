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

from thing.models import CharacterApiScope, MoonConfig, MoonExtraction, MoonExtractionHistory, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

import traceback

class EsiStructures(APITask):
    name = 'thing.structures'

    jumpgate_search_url = 'https://esi.evetech.net/latest/characters/%s/search?categories=structure&language=en-us&search=%%20%%C2%%BB%%20&strict=false'
    structure_url = 'https://esi.evetech.net/latest/universe/structures/%s/?datasource=tranquility'
    corp_structures_url = 'https://esi.evetech.net/latest/corporations/%s/structures/?datasource=tranquility&language=en-us&page=%s'

    def run(self):
        self.init()

        structure_scopes = CharacterApiScope.objects.filter(scope='esi-corporations.read_structures.v1')

        search_scopes = CharacterApiScope.objects.filter(scope='esi-search.search_structures.v1')

        seen_corps = set()

        for scope in structure_scopes:
            char = scope.character

            if 'Station_Manager' in char.get_apiroles():
                if char.corporation_id is not None and char.corporation_id not in seen_corps:
                    success = self.import_structures(char)
                    if success:
                        seen_corps.add(char.corporation_id)

        for scope in search_scopes:
            char = scope.character
            if char.name == 'KenGeorge Beck':
                self.import_jumpgates(char)



    def import_structures(self, character):
        corp_id = character.corporation_id

        page = 1
        max_pages = None
        seen_ids = set()

        skip_updates = False

        while max_pages is None or page < max_pages:
            success, results, headers = self.fetch_esi_url(self.corp_structures_url % (corp_id, page), character, 'get', None, ['x-pages'])

            if not success:
                skip_updates = True
                return False

            if 'x-pages' in headers:
                max_pages = int(headers['x-pages'])
            else:
                max_pages = 1
            page += 1
            structure_info = json.loads(results)

            if len(structure_info) == 0:
                break

            for struct in structure_info:
                struct_id = struct['structure_id']
                
                seen_ids.add(struct_id)
            
                db_station = Station.objects.filter(id=struct_id).first()

                db_struct = Structure.objects.filter(station_id=struct_id).first()

                if db_struct is None:
                    db_struct = Structure(
                        station_id=struct['structure_id'],
                        profile_id=struct['profile_id'],
                    )

                try:
                    success, results = self.fetch_esi_url(self.structure_url % struct['structure_id'], character)
                except:
                    continue

                if success:
                    info = json.loads(results)
                else:
                    #self.log_debug("Cannot find info on structure: %s" % struct['structure_id'])a
                    continue

                if info is None:
                    continue

                if db_station is None:
                    db_station = Station(
                        id=struct['structure_id'],
                    )

                db_station.name = info['name']
                db_station.type_id = struct['type_id']
                db_station.corporation_id = struct['corporation_id']
                db_station.is_citadel = True
                db_station.is_unknown = False
                db_station.system_id = info['solar_system_id']
                db_station.save()

                db_struct.x = info['position']['x']
                db_struct.y = info['position']['y']
                db_struct.z = info['position']['z']

                closest_celestial_id = dictfetchall(queries.closest_celestial % (
                    info['solar_system_id'], db_struct.x,
                    db_struct.y, db_struct.z))[0]['item_id']

                db_struct.closest_celestial_id = closest_celestial_id

                if 'fuel_expires' in struct:
                    db_struct.fuel_expires=self.parse_api_date(struct['fuel_expires'], True)

                if 'state_timer_start' in struct:
                    db_struct.state_timer_start=self.parse_api_date(struct['state_timer_start'], True)
                
                if 'state_timer_end' in struct:
                    db_struct.state_timer_end=self.parse_api_date(struct['state_timer_end'], True)

                db_struct.state = struct['state']
                if 'unanchors_at' in struct:
                    db_struct.unanchors_at = self.parse_api_date(struct['unanchors_at'], True)

                db_struct.save()

                if 'services' in struct:
                    StructureService.objects.filter(structure_id=db_struct.station_id).delete()
                    for service in struct['services']:
                        db_service = StructureService(
                            structure_id=struct['structure_id'],
                            name=service['name'],
                            state=service['state'],
                        )

                        db_service.save()

        if not skip_updates and len(seen_ids) > 0:
            Station.objects.filter(corporation_id=corp_id).exclude(id__in=list(seen_ids)).update(corporation_id=None)
            Station.objects.filter(corporation_id=corp_id, id__in=list(seen_ids)).update(deleted=False)

        # Loop through all citadels with no corporation and determine corporation
        # If a 403 Forbidden is returned, delete the citadel
        # If the corporation ID matches the current import corporation, delete the citadel
        # If the corporation ID is a different corporation, update corporation_id
        unknown_citadels = Station.objects.filter(is_citadel=True, corporation_id__isnull=True, deleted=False)

        batch_size = 25

        for i in range(0, len(unknown_citadels), batch_size):
            citadels = unknown_citadels[i:batch_size+i]

            urls = [self.structure_url % c.id for c in citadels]

            lookup = dict((self.structure_url % c.id, c) for c in citadels)

            print('Retrieving %d-%d of %d' % (i+1, batch_size+i, len(unknown_citadels)))

            batch_results = self.fetch_batch_esi_urls(urls, character, batch_size=5, headers_to_return=['status'])

            for url, c_data in batch_results.items():
                success, results, headers = c_data

                c = lookup[url]
                if 'status' in headers and headers['status'] == 404:
                    # Forbidden, delete entry
                    print('Deleting %s [%d]' % (c.name, c.id))
                    c.deleted = True
                    c.save()
                    continue
                elif not success:
                    print(headers)
                    print('Failed to determine status of %s [%d]' % (c.name, c.id))
                    continue

                structure_info = json.loads(results)

                c.name = structure_info['name']
                c.type_id = structure_info['type_id']
                c.system_id = structure_info['solar_system_id']

                if structure_info['owner_id'] == character.corporation_id:
                    print('Deleting corp structure %s [%d]' % (c.name, c.id))
                    c.deleted = True
                    c.save()
                    continue

                print('Updating corp for structure %s [%d]' % (c.name, c.id))

                c.corporation_id = structure_info['owner_id']
                c.save()
        
        return True
                


    def import_jumpgates(self, character):
        # Get jump gates
        success, result = self.fetch_esi_url(self.jumpgate_search_url % character.id, character)
        if not success:
            print(result)
            return True

        data = json.loads(result)

        for jg_id in data['structure']:
            #if jg_id in seen_ids:
            #    continue

            success, jg_result = self.fetch_esi_url(self.structure_url % jg_id, character)
            if not success:
                continue

            jg = json.loads(jg_result)

            station = Station.objects.filter(id=jg_id).first()
            if station is None:
                station = Station()
                station.id = jg_id
                station.name = jg['name']
                station.type_id = jg['type_id']
                station.system_id = jg['solar_system_id']
                station.corporation_id = jg['owner_id']
                station.is_unknown = False
                station.is_citadel = True

            if station.is_thirdparty:
                station.is_thirdparty = station.corporation_id != character.corporation_id
            station.deleted = False
            station.save()

        Station.objects.filter(type_id=35841, is_thirdparty=True).exclude(corporation_id=character.corporation_id).exclude(id__in=data['structure']).update(deleted=True)

        return True
