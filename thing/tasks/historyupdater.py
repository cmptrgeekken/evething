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
from thing.models.buybackitemgroup import BuybackItemGroup

import json

HISTORY_PER_REQUEST = 50


class HistoryUpdater(APITask):
    name = 'thing.history_updater'

    history_url = 'https://esi.evetech.net/latest/markets/%s/history/?datasource=tranquility&type_id=%s'

    def run(self, item_ids=None, region_id=None):
        self.init()

        if item_ids is not None:
            items = [dict(item_id=i, region_id=region_id) for i in item_ids]
        else:
            # Get a list of all item_ids
            cursor = self.get_cursor()
            cursor.execute(queries.pricing_item_ids)

            items = [dict(item_id=row[0], region_id=row[1]) for row in cursor]

            cursor.close()

        urls = [self.history_url % (i['region_id'], i['item_id']) for i in items]

        item_lookup = dict()
        for i in range(0, len(urls)):
            item_lookup[urls[i]] = items[i]['region_id'], items[i]['item_id']

        all_history_data = self.fetch_batch_esi_urls(urls, None)

        # Collect data
        for url, history_data in all_history_data.items():
            success, data = history_data

            if not success:
                return

            item_history = json.loads(data)

            region_id, item_id = item_lookup[url]

            data = {}
            for history in item_history:
                data[history['date']] = history

            for ph in PriceHistory.objects.filter(region=region_id, item=item_id, date__in=data.keys()):
                del data[str(ph.date)]

            new = []
            for date, history in data.items():
                new.append(PriceHistory(
                    region_id=region_id,
                    item_id=item_id,
                    date=history['date'],
                    minimum=history['lowest'],
                    maximum=history['highest'],
                    average=history['average'],
                    movement=history['volume'],
                    orders=history['order_count'],
                ))

            if new:
                PriceHistory.objects.bulk_create(new)

        return True
