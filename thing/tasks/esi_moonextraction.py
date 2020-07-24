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
import urllib2

from .apitask import APITask
import json

from thing.models import CharacterApiScope, MoonConfig, MoonExtraction, MoonExtractionHistory, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

import traceback

class EsiMoonExtraction(APITask):
    name = 'thing.moonextraction'

    mining_url = 'https://esi.evetech.net/latest/corporation/%s/mining/extractions/?datasource=tranquility'
    write_structure_url = 'https://esi.evetech.net/latest/corporations/%s/structures/%s/?datasource=tranquility&language=en-us'
    micrim_url = 'http://ph.infinity-bay.com/kgb.php'

    def run(self):
        self.init()

        extract_scopes = CharacterApiScope.objects.filter(scope='esi-industry.read_corporation_mining.v1')
        write_struct_scopes = CharacterApiScope.objects.filter(scope='esi-corporations.write_structures.v1')

        seen_corps = set()

        for scope in extract_scopes:
            char = scope.character

            if 'Director' in char.get_apiroles():
                if char.corporation_id is not None and char.corporation_id not in seen_corps:
                    if self.import_moon(char):
                        seen_corps.add(char.corporation_id)

        '''
        seen_corps = set()

        for scope in write_struct_scopes:
            char = scope.character

            if 'Station_Manager' in char.get_apiroles():
                if char.corporation_id not in seen_corps:
                    self.update_vuln_schedule(char)
                    seen_corps.add(char.corporation_id)
        '''
        # Update from Micrim's dump
        response = urllib2.urlopen(self.micrim_url)
        data = response.read()

        moon_data = json.loads(data)
        for d in moon_data:
            cfg = MoonConfig.objects.filter(structure__station_id=d['structure_id']).first()
            if cfg is None:
                cfg = MoonConfig()
                cfg.is_nationalized = False
            cfg.next_date_override = d['planned_chunk']

            print('Updating %s: %s' % (cfg.structure.station.name, cfg.next_date_override))

            cfg.save()

    def update_vuln_schedule(self, character):
        corp_id = character.corporation_id

        extractions = MoonExtraction.objects.filter(structure__station__corporation_id=corp_id)

        old_vuln_times = []

        for i in range(0, 4):
            for j in range(7, 12):
                old_vuln_times.append(dict(day=i, hour=j))

        for e in extractions:
            day_of_week = e.chunk_arrival_time.weekday()
            hour_of_day = e.chunk_arrival_time.hour

            cfg = MoonConfig.objects.filter(structure_id=e.structure.id, ignore_scheduling=0).exclude(configured_vuln_date=day_of_week, configured_vuln_hour=hour_of_day).first()
            if cfg is None:
                continue

            vuln_times = []

            for i in range(0, 20):
                hour = (hour_of_day + i) % 24
                day = (day_of_week + ((hour_of_day + i) / 24)) % 7

                vuln_times.append(dict(day=day, hour=hour))

            try:
                success, result = self.fetch_esi_url(self.write_structure_url % (corp_id, e.structure_id), character, method='put', body=vuln_times)

                if success:
                    cfg.configured_vuln_date = day_of_week
                    cfg.configured_vuln_hour = hour_of_day
                    cfg.save()
            except Exception, e:
                print(e)
                print(e.structure_id)
                pass

    def import_moon(self, character):
        corp_id = character.corporation_id

        try:
            success, results = self.fetch_esi_url(self.mining_url % corp_id, character)

            if not success:
                print(character.name)
                print(results)
                return False

            mining_info = json.loads(results)

            seen_moons = dict()

            for info in mining_info:
                db_moonextract = MoonExtraction.objects.filter(moon_id=info['moon_id']).first()
                if db_moonextract is None:
                    db_moonextract = MoonExtraction(
                        moon_id=info['moon_id'],
                    )

                db_moonextract.extraction_start_time = self.parse_api_date(info['extraction_start_time'], True)
                db_moonextract.chunk_arrival_time = self.parse_api_date(info['chunk_arrival_time'], True)
                db_moonextract.natural_decay_time = self.parse_api_date(info['natural_decay_time'], True)
                db_moonextract.structure_id = info['structure_id']

                db_extracthistory = MoonExtractionHistory.objects.filter(structure_id=info['structure_id'], chunk_arrival_time__gte=db_moonextract.chunk_arrival_time-datetime.timedelta(minutes=10), chunk_arrival_time__lte=db_moonextract.chunk_arrival_time+datetime.timedelta(minutes=10)).first()
                chunk_minutes = (db_moonextract.chunk_arrival_time - db_moonextract.extraction_start_time).total_seconds() / 60.0

                if db_extracthistory is None:
                    db_extracthistory = MoonExtractionHistory(
                        moon_id=info['moon_id'],
                        structure_id=info['structure_id'],
                    )

                db_extracthistory.extraction_start_time=db_moonextract.extraction_start_time
                db_extracthistory.chunk_arrival_time=db_moonextract.chunk_arrival_time
                db_extracthistory.natural_decay_time=db_moonextract.natural_decay_time
                db_extracthistory.chunk_minutes=chunk_minutes

                db_extracthistory.save()

                db_moonextract.save()

                seen_moons[db_extracthistory.structure_id] = db_extracthistory.chunk_arrival_time
        except Exception, e:
            traceback.print_exc(e)
            return True

        if len(seen_moons) > 0:
            bad_moons = MoonExtractionHistory.objects.filter(structure__station__corporation_id=corp_id, chunk_arrival_time__gt=datetime.datetime.utcnow()).exclude(structure_id__in=seen_moons.keys()).delete()

            for k in seen_moons:
                t = seen_moons[k]

                MoonExtractionHistory.objects.filter(structure_id=k, chunk_arrival_time__gt=datetime.datetime.utcnow()).exclude(chunk_arrival_time=t).delete()


        return True
