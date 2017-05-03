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

from decimal import Decimal
from datetime import datetime,timedelta

import json
from thing.models import ItemOrder

PRICE_PER_REQUEST = 100
PRICE_STATION_ID = 60003760  # Jita 4-4
PRICE_REGION_ID = 10000002  # The Forge


class PriceUpdater(APITask):
    name = 'thing.price_updater'

    def run(self, api_url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id) is False:
            return

        page_number = 1

        all_orders = dict()

        all_order_ids = []
        while True:
            # Retrieve market data and parse the JSON
            url = api_url % (PRICE_REGION_ID, page_number)
            data = self.fetch_url(url, {})
            if data is False:
                return

            orders = json.loads(data)

            if len(orders) == 0:
                break

            for order in orders:
                # Create the new order object
                remaining = int(order['volume_remain'])
                price = Decimal(order['price'])
                issued = self.parse_api_date(order['issued'], True)

                item_order = ItemOrder(
                    id=int(order['order_id']),
                    item_id=int(order['type_id']),
                    location_id=int(order['location_id']),
                    price=price,
                    total_price=price*remaining,
                    buy_order=order['is_buy_order'],
                    volume_entered=int(order['volume_total']),
                    volume_remaining=remaining,
                    minimum_volume=int(order['min_volume']),
                    issued=issued,
                    expires=issued + timedelta(int(order['duration'])),
                    range=order['range'],
                    last_updated=datetime.utcnow()
                )

                all_order_ids.append(item_order.id)
                all_orders[item_order.id] = item_order

            page_number += 1

        # Find existing orders
        existing_orders = ItemOrder.objects.filter(
            id__in=all_order_ids
        ).values_list('id')

        existing_orders = set([o[0] for o in existing_orders])

        new_orders = []
        updated_orders = []
        for order_id in all_orders:
            order = all_orders[order_id]

            if order_id not in existing_orders:
                new_orders.append(order)
            else:
                updated_orders.append(order)

        # Insert new orders
        ItemOrder.objects.bulk_insert(new_orders)

        # Update existing orders
        ItemOrder.objects.bulk_update(updated_orders, ['price', 'total_price', 'last_updated', 'volume_remaining'])

        # Delete non-existent orders:
        ItemOrder.objects.exclude(id__in=all_order_ids).delete()

        return True
