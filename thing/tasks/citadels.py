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

from thing.models import Station, System
import json


class Citadels(APITask):
    name = 'thing.citadels'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id) is False:
            return

        data = self.fetch_url(url, {})
        citadels = json.loads(data)

        station_map = Station.objects.in_bulk(citadels.keys())

        new_citadels = []
        for citadel_id in citadels:
            citadel = citadels[citadel_id]
            existing_citadel = station_map.get(citadel_id)
            if existing_citadel is None:
                new_citadel = Station(
                    id=citadel_id,
                    name=citadel['name'],
                    system_id=citadel['systemId'],
                    is_citadel=True
                )

                new_citadels.append(new_citadel)
            elif existing_citadel.is_unknown is True:
                existing_citadel.name = citadel['name']
                existing_citadel.is_unknown = False
                existing_citadel.is_citadel = True

                existing_citadel.save()

        if new_citadels:
            Station.objects.bulk_create(new_citadels)

        return True
