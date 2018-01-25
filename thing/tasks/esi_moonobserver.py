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

from thing.models import Character, Corporation, CharacterApiScope, MoonObserver, MoonObserverEntry
from thing import queries
from thing.utils import dictfetchall

import traceback


class EsiMoonObserver(APITask):
    name = 'thing.moonobserver'

    corporation_url = 'https://esi.tech.ccp.is/latest/corporation/%s/'
    character_url = 'https://esi.tech.ccp.is/latest/characters/%s/'

    observer_url = 'https://esi.tech.ccp.is/latest/corporation/%s/mining/observers/?datasource=tranquility&page=%s'
    observer_detail_url = 'https://esi.tech.ccp.is/latest/corporation/%s/mining/observers/%s/?datasource=tranquility&page=%s'

    def run(self, base_url):
        self.init()

        extract_scope_chars = [s.character for s in CharacterApiScope.objects.filter(scope='esi-industry.read_corporation_mining.v1')]

        seen_corps = set()

        for char in extract_scope_chars:
            if 'Accountant' in char.get_apiroles():
                if char.corporation_id not in seen_corps:
                    seen_corps.add(char.corporation_id)
                    self.import_observers(char)

    def import_observers(self, character):
        corp_id = character.corporation.id
        refresh_token = character.sso_refresh_token

        access_token, expires = self.get_access_token(refresh_token)

        page = 1
        try:
            while True:
                if expires <= datetime.datetime.now():
                    access_token, expires = self.get_access_token(refresh_token)

                results = self.fetch_esi_url(self.observer_url % (corp_id, page), access_token)
                page += 1
                observers = json.loads(results)

                if len(observers) == 0:
                    break

                for observer in observers:
                    db_observer = MoonObserver.objects.filter(observer_id=observer['observer_id']).first()

                    do_import = True

                    current_time = datetime.datetime.utcnow()

                    if db_observer is None:
                        db_observer = MoonObserver(
                            observer_id=observer['observer_id'],
                            observer_type=observer['observer_type'],
                            last_updated=observer['last_updated'],
                        )

                        db_observer.save()

                    if do_import:
                        inner_page = 1
                        results, headers = self.fetch_esi_url(
                            url=self.observer_detail_url % (corp_id, db_observer.observer_id, inner_page),
                            access_token=access_token,
                            headers_to_return=['Last-Modified'])
                        inner_page += 1

                        if headers['Last-Modified']:
                            observer_time = self.parse_esi_date(headers['Last-Modified'])
                        else:
                            observer_time = datetime.datetime.utcnow()

                        observer_details = json.loads(results)

                        for detail in observer_details:
                            corp = Corporation.objects.filter(id=detail['recorded_corporation_id']).first()
                            if corp is None:
                                corp = Corporation(
                                    id=detail['recorded_corporation_id'],
                                    name='*UNKNOWN*',
                                )

                                corp.save()

                            char = Character.objects.filter(id=detail['character_id']).first()
                            if char is None:
                                char = Character(
                                    id=detail['character_id'],
                                    name='*UNKNOWN*',
                                    corporation_id=detail['recorded_corporation_id'],
                                )

                                char.save()

                            db_entry = MoonObserverEntry.objects.filter(
                                observer_id=db_observer.id,
                                character_id=detail['character_id'],
                                type_id=detail['type_id'],
                                last_updated=detail['last_updated']).first()

                            if db_entry is None:
                                db_entry = MoonObserverEntry(
                                    observer_id=db_observer.id,
                                    character_id=detail['character_id'],
                                    recorded_corporation_id=detail['recorded_corporation_id'],
                                    type_id=detail['type_id'],
                                    times_updated=0,
                                    start_time=observer_time,
                                    end_time=observer_time,

                                )
                            elif db_entry.quantity != detail['quantity']:
                                db_entry.times_updated += 1
                                db_entry.end_time = observer_time

                            db_entry.last_updated = detail['last_updated']
                            db_entry.quantity = detail['quantity']
                            db_entry.save()

                        db_observer.last_updated = observer['last_updated']
                        db_observer.save()
        except Exception, e:
            traceback.print_exc(e)
            return True

        return True
