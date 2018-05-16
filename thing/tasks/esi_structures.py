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

    structure_url = 'https://esi.tech.ccp.is/latest/universe/structures/%s/?datasource=tranquility'
    corp_structures_url = 'https://esi.tech.ccp.is/latest/corporations/%s/structures/?datasource=tranquility&language=en-us&page=%s'

    def run(self):
        self.init()

        structure_scopes = CharacterApiScope.objects.filter(scope='esi-corporations.read_structures.v1')

        seen_corps = set()

        for scope in structure_scopes:
            char = scope.character

            if 'Station_Manager' in char.get_apiroles():
                if char.corporation_id is not None and char.corporation_id not in seen_corps:
                    self.import_structures(char)
                    seen_corps.add(char.corporation_id)

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
                break

            max_pages = int(headers['x-pages'])
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
                    self.log_debug("Cannot find info on structure: %s" % struct['structure_id'])
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

                db_struct.save()

                StructureService.objects.filter(structure_id=db_struct.station_id).delete()
                if 'services' in struct:
                    for service in struct['services']:
                        db_service = StructureService(
                            structure_id=struct['structure_id'],
                            name=service['name'],
                            state=service['state'],
                        )

                        db_service.save()

        if not skip_updates:
            Station.objects.filter(corporation_id=corp_id).exclude(id__in=list(seen_ids)).update(corporation_id=None)

        return True
