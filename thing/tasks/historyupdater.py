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

from thing import queries
from thing.models import PriceHistory

import json

HISTORY_PER_REQUEST = 50

REGION_ID = 10000002


class HistoryUpdater(APITask):
    name = 'thing.history_updater'

    def run(self, api_url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id) is False:
            return

        # Get a list of all item_ids
        cursor = self.get_cursor()
        cursor.execute(queries.pricing_item_ids)

        item_ids = [row[0] for row in cursor]

        cursor.close()

        # Collect data
        new = []
        for i in range(0, len(item_ids)):
            item_id = item_ids[i]
            # Fetch the XML
            url = api_url % (REGION_ID, item_id)
            data = self.fetch_url(url, {})
            if data is False:
                return

            item_history = json.loads(data)

            data = {}
            for history in item_history:
                data[history['date']] = history

            for ph in PriceHistory.objects.filter(region=REGION_ID,item=item_id,date__in=data.keys()):
                del data[str(ph.date)]

            for date, history in data.items():
                new.append(PriceHistory(
                    region_id = REGION_ID,
                    item_id = item_id,
                    date = history['date'],
                    minimum = history['lowest'],
                    maximum = history['highest'],
                    average = history['average'],
                    movement = history['volume'],
                    orders = history['order_count']
                ))

        if new:
            PriceHistory.objects.bulk_create(new)

        return True
