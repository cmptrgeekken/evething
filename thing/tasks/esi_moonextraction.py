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

from thing.models import CharacterApiScope, MoonConfig, MoonExtraction, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

import traceback

class EsiMoonExtraction(APITask):
    name = 'thing.moonextraction'

    mining_url = 'https://esi.tech.ccp.is/latest/corporation/%s/mining/extractions/?datasource=tranquility'
    structure_url = 'https://esi.tech.ccp.is/latest/universe/structures/%s/?datasource=tranquility'
    corp_structures_url = 'https://esi.tech.ccp.is/latest/corporations/%s/structures/?datasource=tranquility&language=en-us&page=%s'

    def run(self, base_url):
        self.init()

        extract_scopes = CharacterApiScope.objects.filter(scope='esi-industry.read_corporation_mining.v1')

        structure_scopes = CharacterApiScope.objects.filter(scope='esi-corporations.read_structures.v1')

        seen_corps = set()

        for scope in structure_scopes:
            char = scope.character

            if 'Station_Manager' in char.get_apiroles():
                if char.corporation_id not in seen_corps:

                    self.import_structures(char)
                    seen_corps.add(char.corporation_id)

        seen_corps = set()

        for scope in extract_scopes:
            char = scope.character

            if 'Director' in char.get_apiroles():
                if char.corporation_id not in seen_corps:
                    self.import_moon(char)
                    seen_corps.add(char.corporation_id)

    def import_moon(self, character):
        corp_id = character.corporation.id
        refresh_token = character.sso_refresh_token

        access_token, expires = self.get_access_token(refresh_token)

        try:
            if expires <= datetime.datetime.now():
                access_token, expires = self.get_access_token(refresh_token)

            results = self.fetch_esi_url(self.mining_url % corp_id, access_token)

            mining_info = json.loads(results)

            for info in mining_info:
                db_moonextract = MoonExtraction.objects.filter(moon_id=info['moon_id']).first()
                if db_moonextract is None:
                    db_moonextract = MoonExtraction(
                        moon_id=info['moon_id'],
                    )

                db_moonconfig = MoonConfig.objects.filter(structure__station_id=info['structure_id']).first()

                if db_moonconfig is not None:
                    if db_moonextract.chunk_arrival_time < self.parse_api_date(info['chunk_arrival_time'], True)\
                            or db_moonconfig.last_chunk_time is None:
                        chunk_diff = (
                                     db_moonextract.chunk_arrival_time - db_moonextract.extraction_start_time).total_seconds() / 60.0
                        db_moonconfig.last_chunk_time = db_moonextract.chunk_arrival_time
                        db_moonconfig.last_chunk_minutes = chunk_diff
                        db_moonconfig.save()

                db_moonextract.extraction_start_time = self.parse_api_date(info['extraction_start_time'], True)
                db_moonextract.chunk_arrival_time = self.parse_api_date(info['chunk_arrival_time'], True)
                db_moonextract.natural_decay_time = self.parse_api_date(info['natural_decay_time'], True)
                db_moonextract.structure_id = info['structure_id']

                db_moonextract.save()
        except Exception, e:
            traceback.print_exc(e)
            return True

        return True

    def import_structures(self, character):
        corp_id = character.corporation.id
        refresh_token = character.sso_refresh_token

        access_token, expires = self.get_access_token(refresh_token)

        page = 1
        try:
            while True:
                if expires <= datetime.datetime.now():
                    access_token, expires = self.get_access_token(refresh_token)

                results = self.fetch_esi_url(self.corp_structures_url % (corp_id, page), access_token)
                page += 1
                structure_info = json.loads(results)

                if len(structure_info) == 0:
                    break

                for struct in structure_info:
                    db_station = Station.objects.filter(id=struct['structure_id']).first()

                    db_struct = Structure.objects.filter(station_id=struct['structure_id']).first()

                    if db_struct is None\
                            or db_station is None\
                            or db_station.corporation_id is None\
                            or db_station.is_unknown:

                        if db_struct is None:
                            db_struct = Structure(
                                station_id=struct['structure_id'],
                                profile_id=struct['profile_id'],
                            )

                        if expires <= datetime.datetime.now():
                            access_token, expires = self.get_access_token(refresh_token)

                        results = self.fetch_esi_url(self.structure_url % struct['structure_id'], access_token)

                        info = None

                        try:
                            info = json.loads(results)
                        except:
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

                    db_struct.state_timer_start=self.parse_api_date(struct['state_timer_start'], True)
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
        except Exception,e:
            traceback.print_exc(e)
            return True

        return True
