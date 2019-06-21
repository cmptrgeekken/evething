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

import json

from thing.models import *

# Periodic task to try to fix *UNKNOWN* Character objects
CHAR_NAME_URL = 'https://esi.evetech.net/latest/characters/names/'
CHAR_INFO_URL = 'https://esi.evetech.net/latest/characters/%s/'
CORP_NAME_URL = 'https://esi.evetech.net/latest/corporations/names/'
IDS_TO_NAMES_URL = 'https://esi.evetech.net/latest/universe/names/'


class FixNames(APITask):
    name = 'thing.fix_names'

    def run(self):
        self.init()

        # Fetch all unknown Character objects
        char_map = {}
        for char in Character.objects.filter(name='*UNKNOWN*', not_found=False):
            char_map[char.id] = char

        # Fetch all Characters without Corporations
        no_corp_map = {}
        for char in Character.objects.filter(corporation_id=None, not_found=False):
            no_corp_map[char.id] = char

        # Fetch all unknown Corporation objects
        corp_map = {}
        for corp in Corporation.objects.filter(name='*UNKNOWN*'):
            corp_map[corp.id] = corp

        ids = list(set(char_map.keys()) | set(corp_map.keys()))

        # Go fetch names for them
        name_map = {}
        for i in range(0, len(ids), 1000):
            bodies = [[id] for id in ids[i:i+1000]]


            response_data = self.post_batch_esi_urls(IDS_TO_NAMES_URL, bodies)

            for name_data in response_data:
                success, response = name_data

                if not success:
                    print(response)
                    continue

                result = json.loads(response)

                for row in result:
                    cat = row['category']
                    name = row['name']
                    id = int(row['id'])
                    name_map[id] = name

                    if cat == 'character':
                        char = char_map.get(id)
                        if char:
                            char.name = name
                            char.save()
                            continue
                    elif cat == 'corporation':
                        corp = corp_map.get(id)
                        if corp:
                            corp.name = name
                            corp.save()
                            continue

                    print('Map invalid: %s' % row)

        Character.objects.filter(name='*UNKNOWN*', not_found=False).update(not_found=True)

        urls = [CHAR_INFO_URL % id for id,char in no_corp_map.items()]
        chars = dict((CHAR_INFO_URL % id, char) for id, char in no_corp_map.items())

        for i in range(0, len(urls), 1000):
            batch_urls = urls[i:i+1000]
            print('Retrieving %d-%d of %d' % (i,i+1000, len(urls)))

            char_info_data = self.fetch_batch_esi_urls(batch_urls, headers_to_return=['status'])
            for url, char_info in char_info_data.items():
                success, response, headers = char_info

                char = chars[url]

                if not success:
                    if 'status' in headers and headers['status'] == 404:
                        char.not_found=True
                        char.save()
                    continue

                result = json.loads(response)

                char.name = result['name']
                char.corporation_id = result['corporation_id']
                char.save()

        # And finally delete any characters that have equivalent corporations now
        cursor = self.get_cursor()
        cursor.execute('DELETE FROM thing_character WHERE id IN (SELECT id FROM thing_corporation)')
        cursor.close()

        return True
