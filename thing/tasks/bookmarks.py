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

from thing.models import Item, Station

import re


class Bookmarks(APITask):
    name = 'thing.bookmarks'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        params = {'characterID': character_id}
        if self.fetch_api(url, params) is False or self.root is None:
            return

        item_groups = ['Citadel', 'Engineering Complex', 'Refinery']

        valid_types_query = Item.objects.filter(item_group__name__in=item_groups)

        valid_types = set([i.id for i in valid_types_query])

        for folder in self.root.findall('result/rowset/row'):
            for bm in folder.findall('rowset/row'):
                location_id = int(bm.attrib['locationID'])
                type_id = int(bm.attrib['typeID'])
                item_id = int(bm.attrib['itemID'])
                x = float(bm.attrib['x'])
                y = float(bm.attrib['y'])
                z = float(bm.attrib['z'])
                memo = bm.attrib['memo']
                note = bm.attrib['note']

                is_valid_name = False

                for g in item_groups:
                    if memo.endswith('( %s )' % g):
                        is_valid_name = True
                        break

                if not is_valid_name:
                    continue

                memo = re.sub(r"\( [^)]+ \)$", '', memo)

                if item_id > 0 and type_id in valid_types:
                    station = Station.objects.filter(id=item_id).first()

                    if station is not None:
                        station.name = memo
                        station.system_id = location_id
                        station.is_unknown = False
                        station.type_id = type_id
                    else:
                        station = Station(
                            id=item_id,
                            name=memo,
                            system_id=location_id,
                            type_id=type_id,
                            is_unknown=False,
                            is_citadel=True
                        )
                    station.save()

        return True
