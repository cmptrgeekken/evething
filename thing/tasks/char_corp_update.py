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

# Periodic task to try to fix *UNKNOWN* Character objects
CHAR_NAME_URL = 'https://esi.evetech.net/latest/characters/names/'
CHAR_INFO_URL = 'https://esi.evetech.net/latest/characters/%s/'
CORP_NAME_URL = 'https://esi.evetech.net/latest/corporations/names/'
AFFILIATION_URL = 'https://esi.evetech.net/latest/characters/affiliation/'
IDS_TO_NAMES_URL = 'https://esi.evetech.net/latest/universe/names/'


class CharCorpUpdate(APITask):
    name = 'thing.char_corp_update'

    def run(self):
        self.init()

        count = Character.objects.filter(Q(corporation_id=None) | Q(last_updated__lte=datetime.datetime.now() - datetime.timedelta(days=1)),not_found=False).exclude(name='*UNKNOWN*').count()

        self.doit()

    def doit(self):
        
        # Fetch chars to update corps
        no_corp_map = {}
        for char in Character.objects.filter(Q(corporation_id=None) | Q(last_updated__lte=datetime.datetime.now() - datetime.timedelta(days=1)),not_found=False).exclude(name='*UNKNOWN*').order_by('corporation_id')[0:10000]:
            no_corp_map[char.id] = char

        # Fetch all unknown Corporation objects
        corp_map = {}
        for corp in Corporation.objects.exclude(name='*UNKNOWN*'):
            corp_map[corp.id] = corp


        urls = [CHAR_INFO_URL % id for id,char in no_corp_map.items()]
        chars = dict((CHAR_INFO_URL % id, char) for id, char in no_corp_map.items())

        ids = no_corp_map.keys()

        bodies = [ids[i:i+1000] for i in range(0, len(ids), 1000)]

        response_data = self.post_batch_esi_urls(AFFILIATION_URL, bodies, headers_to_return=['status'])
        for affiliate_data in response_data:
            success, response, headers = affiliate_data

            if not success:
                print("Failed: %s" % response)
                #if 'status' in headers and headers['status'] == 404:
                    # print('Char not found: %s' % char.name)
                    # char.not_found=True
                    # char.save()
                continue

            result = json.loads(response)

            for row in result:
                char_id = row['character_id']
                corp_id = row['corporation_id']
                alliance_id = row['alliance_id'] if 'alliance_id' in row else None

                char = no_corp_map.get(char_id)
                if char.corporation_id != corp_id:
                    char.corporation_id = corp_id
                char.save()

                corp = corp_map.get(corp_id)
                if corp is not None and corp.alliance_id != alliance_id:
                    corp.alliance_id = alliance_id
                    corp.save()

        return True
