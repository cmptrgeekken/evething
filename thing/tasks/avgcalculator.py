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

from django.db import connections

from thing.models import StationOrder, Item
from thing import queries



class AvgCalculator(APITask):
    name = 'thing.avg_calculator'

    def run(self):
        self.init()

        order_summary = dictfetchall(queries.stationorder_analysis)

        for order in order_summary:
            item_id = order['id']
            sell_ct = int(order['sell_order_ct'])
            sell_volume = int(order['sell_market_volume'])
            sell_min = order['sell_min_price']
            sell_avg = order['sell_avg_price']
            buy_ct = int(order['buy_order_ct'])
            buy_volume = int(order['buy_market_volume'])
            buy_max = order['buy_max_price']
            buy_avg = order['buy_avg_price']

            sell_orders = StationOrder.objects.filter(
                item_id=item_id, buy_order=0).order_by('price')
            buy_orders = StationOrder.objects.filter(
                item_id=item_id, buy_order=1).order_by('-price')

            sell_fivepct_volume = int(sell_volume * 0.05)
            buy_fivepct_volume = int(buy_volume * 0.05)

            fivepct_total = 0
            fivepct_running_volume = sell_fivepct_volume
            for sell in sell_orders:
                diff = min(sell.volume_remaining, fivepct_running_volume)
                if diff > 0:
                    fivepct_total += diff * sell.price
                    fivepct_running_volume -= diff
                else:
                    break

            fivepct_total = 0
            fivepct_running_volume = buy_fivepct_volume
            for buy in buy_orders:
                diff = min(buy.volume_remaining, fivepct_running_volume)
                if diff > 0:
                    fivepct_total += diff * buy.price
                    fivepct_running_volume -= diff
                else:
                    break

            item = Item.objects.filter(id=item_id).first()

            item.sell_total_volume = sell_volume
            item.sell_avg_price = sell_avg
            if sell_fivepct_volume > 0:
                item.sell_fivepct_price = fivepct_total / sell_fivepct_volume
                item.sell_fivepct_volume = sell_fivepct_volume

            item.buy_total_volume = buy_volume
            item.buy_avg_price = buy_avg
            if buy_fivepct_volume > 0:
                item.buy_fivepct_price = fivepct_total / buy_fivepct_volume
                item.buy_fivepct_volume = buy_fivepct_volume

            item.save()

        return True


def get_cursor(db='default'):
    return connections[db].cursor()


def dictfetchall(query):
    "Returns all rows from a cursor as a dict"
    cursor = get_cursor()
    cursor.execute(query)
    desc = cursor.description
    results = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    return results