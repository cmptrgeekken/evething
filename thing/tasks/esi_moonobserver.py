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

    corporation_url = 'https://esi.evetech.net/latest/corporation/%s/'
    character_url = 'https://esi.evetech.net/latest/characters/%s/'

    observer_url = 'https://esi.evetech.net/latest/corporation/%s/mining/observers/?datasource=tranquility&page=%s'
    observer_detail_url = 'https://esi.evetech.net/latest/corporation/%s/mining/observers/%s/?datasource=tranquility&page=%s'

    def run(self):
        self.init()

        extract_scope_chars = [s.character for s in CharacterApiScope.objects.filter(scope='esi-industry.read_corporation_mining.v1')]

        seen_corps = set()

        for char in extract_scope_chars:
            if 'Accountant' in char.get_apiroles():
                if char.corporation_id is not None and char.corporation_id not in seen_corps:
                    if self.import_observers(char):
                        seen_corps.add(char.corporation_id)

    def import_observers(self, character):
        corp_id = character.corporation_id

        page = 1
        max_pages = None
        try:
            while max_pages is None or page <= max_pages:

                success, results, headers = self.fetch_esi_url(self.observer_url % (corp_id, page), character, headers_to_return=['x-pages'])
                if 'x-pages' in headers:
                    max_pages = int(headers['x-pages'])

                if not success:
                    print(character.name)
                    print(results)
                    return False
                
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
                        initial_url = self.observer_detail_url % (corp_id, db_observer.observer_id, 1)
                        success, results, headers = self.fetch_esi_url(
                            url=initial_url,
                            character=character,
                            headers_to_return=['last-modified', 'x-pages'])

                        if not success:
                            continue

                        if 'last-modified' in headers:
                            observer_time = self.parse_esi_date(headers['last-modified'])
                        else:
                            observer_time = datetime.datetime.utcnow()

                        if 'x-pages' in headers:
                            max_pages = int(headers['x-pages'])
                        else:
                            max_pages = 1

                        urls = [self.observer_detail_url % (corp_id, db_observer.observer_id, p) for p in range(2, max_pages+1)]

                        if max_pages > 1:
                            all_observer_data = self.fetch_batch_esi_urls(urls, character, batch_size=20, headers_to_return=['last-modified'])
                        else:
                            all_observer_data = dict()

                        all_observer_data[initial_url] = (success, results, headers)

                        observer_details = list()

                        for url, observer_data in all_observer_data.items():
                            success, results, headers = observer_data

                            if not success:
                                self.log_warn('Failed to load results: %s' % results)

                            observer_details += json.loads(results)
                        
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
