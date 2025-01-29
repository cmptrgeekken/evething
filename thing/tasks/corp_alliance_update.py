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

from .apitask import APITask

import json,datetime

from thing.models import *
from django.db.models import Q

ALLIANCES_URL = 'https://esi.evetech.net/latest/alliances/%s/'
ALLIANCE_CORPS_URL = 'https://esi.evetech.net/latest/alliances/%s/corporations'

CORPS_URL = 'https://esi.evetech.net/latest/corporations/%s/'

class CorpAllianceUpdate(APITask):
    name = 'thing.corp_alliance_update'

    def run(self):
        self.init()

        self.doit()

    def doit(self):
        # Station ID's that are missing
        station_corp_ids = set(Station.objects.filter(corporation__name=None).values_list('corporation_id', flat=True))

        self.import_corps(None, station_corp_ids)

        current_alliances = Alliance.objects.all().values_list('id', flat=True)

        alliance_corps_urls  = [ALLIANCE_CORPS_URL % id for id in current_alliances]
        alliance_ids = dict((ALLIANCE_CORPS_URL % id, id) for id in current_alliances)

        response_data = self.fetch_batch_esi_urls(alliance_corps_urls, None, batch_size=20)
        for url, alliance_corp_data in response_data.items():
            success, data = alliance_corp_data

            if not success:
                print('Alliance Corps Retrieve failed: %s' % data)
                continue

            corp_ids = json.loads(data)

            self.import_corps(alliance_ids[url], corp_ids)


        return True

    def import_corps(self, alliance_id, corp_ids):

        current_corps = Corporation.objects.filter(id__in=corp_ids).values_list('id', flat=True)

        missing_corp_ids = [id for id in corp_ids if id not in current_corps]

        corps_urls = [CORPS_URL % id for id in missing_corp_ids]
        corp_id_lookup = dict((CORPS_URL % id, id) for id in missing_corp_ids)

        if len(missing_corp_ids) > 0:
            if alliance_id is not None:
                print('Missing Corps for Alliance %d: %d' % (alliance_id, len(missing_corp_ids)))
            else:
                print('Missing Corps: %d' % len(missing_corp_ids))

        corp_response_data = self.fetch_batch_esi_urls(corps_urls, None, batch_size=1)
        for url, corp_data in corp_response_data.items():
            success, data = corp_data

            if not success:
                print('Corp Retrieve failed: %s' % data)
                continue

            corp = json.loads(data)
            corp_id = corp_id_lookup[url]

            db_corp = Corporation()
            db_corp.id = corp_id
            print('New Corp %d: %s (%s)' % (corp_id, corp['name'], corp['alliance_id'] if 'alliance_id' in corp else 'None'))

            if 'alliance_id' in corp:
                db_corp.alliance_id = corp['alliance_id']
            db_corp.name = corp['name']
            db_corp.ticker = corp['ticker']
            db_corp.save()

        Corporation.objects.filter(alliance_id=alliance_id).exclude(id__in=corp_ids).update(alliance_id=None)
        Corporation.objects.filter(id__in=corp_ids).update(alliance_id=alliance_id)

