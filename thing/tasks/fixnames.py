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

        self.doit()

    def doit(self):
        
        # Fetch all unknown Character objects
        char_map = {}
        for char in Character.objects.filter(name='*UNKNOWN*', not_found=False)[0:10000]:
            char_map[char.id] = char

        # Fetch all Characters without Corporations
        #no_corp_map = {}
        #for char in Character.objects.filter(corporation_id=None, not_found=False)[0:10000]:
        #    no_corp_map[char.id] = char

        # Fetch all unknown Corporation objects
        corp_map = {}
        for corp in Corporation.objects.filter(name='*UNKNOWN*'):
            corp_map[corp.id] = corp
        
        cursor = self.get_cursor()

        cursor.execute('SELECT DISTINCT corporation_id FROM thing_character ch left join thing_corporation co on ch.corporation_id=co.id where co.id is null AND ch.corporation_id IS NOT NULL and ch.not_found=0')
        rows = cursor.fetchall()
        
        char_empty_corps = [r[0] for r in rows]

        cursor.execute('select distinct alliance_id from thing_corporation co left join thing_alliance a on co.alliance_id=a.id where a.id is null and co.alliance_id is not null');
        rows = cursor.fetchall()
        corp_empty_alliances = [r[0] for r in rows]

        ids = list(set(char_map.keys()) | set(corp_map.keys()) | set(char_empty_corps) | set(corp_empty_alliances))

        for i in range(0, len(ids), 10):
            bodies = [[id] for id in ids[i:i+10]]

            response_data = self.post_batch_esi_urls(IDS_TO_NAMES_URL, bodies, headers_to_return=['status'])

            for name_data in response_data:
                success, response, headers = name_data

                if not success:
		    if 'status' in headers and headers['status'] == 404:
                        id = headers['request_body'][0]
                        char = char_map.get(id)
                        if char is not None:
                            char.not_found=True
                            char.save()
                    continue

                result = json.loads(response)

                for row in result:
                    cat = row['category']
                    name = row['name']
                    id = int(row['id'])

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
                        else:
                            corp = Corporation()
                            corp.id = id
                            corp.name = name
                            corp.save()
                            continue
                    elif cat == 'alliance':
                        alliance = Alliance()
                        alliance.id = id
                        alliance.name = name
                        alliance.save()
                        continue

                    print('Map invalid: %s' % row)

        Character.objects.filter(name='*UNKNOWN*', not_found=False, id__in=char_map.keys()).update(not_found=True)

        # Update any characters previously marked as not_found
        cursor.execute('update thing_character set not_found=0 where name=\'*UNKNOWN*\' AND id in (select first_party_id from thing_esijournal)');

        # And finally delete any characters that have equivalent corporations now
        cursor.execute('DELETE FROM thing_character WHERE id IN (SELECT id FROM thing_corporation WHERE name != \'*UNKNOWN*\')')
        cursor.close()

        return True
