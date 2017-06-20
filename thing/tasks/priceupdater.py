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
from datetime import datetime, timedelta

import json
from thing.models import Station, StationOrder


class PriceUpdater(APITask):
    name = 'thing.price_updater'

    def run(self, api_url, taskstate_id, apikey_id, station_id):
        if self.init(taskstate_id) is False:
            return

        page_number = 1

        station = Station.objects.filter(id=station_id).first()

        if station is None or station.market_profile is None or station.market_profile.sso_refresh_token is None:
            self.log_warn('No refresh token found for station %d!' % station.id)
            return

        access_token = None
        token_expires = None

        existing_orders = StationOrder.objects.filter(
            station_id=station_id
        ).values_list('id')

        existing_order_ids = set([o[0] for o in existing_orders])

        all_order_ids = []
        while True:
            if access_token is None or token_expires < datetime.now():
                access_token, token_expires = self.get_access_token(station.market_profile.sso_refresh_token)

            # Retrieve market data and parse the JSON
            url = api_url + page_number
            data = self.fetch_esi_url(url, access_token)
            if data is False:
                return

            orders = json.loads(data)

            if len(orders) == 0:
                break

            new_orders = []
            updated_orders = []
            for order in orders:
                # Create the new order object
                remaining = int(order['volume_remain'])
                price = Decimal(order['price'])
                issued = self.parse_api_date(order['issued'], True)

                item_order = StationOrder(
                    id=int(order['order_id']),
                    item_id=int(order['type_id']),
                    station_id=int(order['location_id']),
                    price=price,
                    total_price=price*remaining,
                    buy_order=order['is_buy_order'],
                    volume_entered=int(order['volume_total']),
                    volume_remaining=remaining,
                    minimum_volume=int(order['min_volume']),
                    issued=issued,
                    expires=issued + timedelta(int(order['duration'])),
                    range=order['range']
                )

                if item_order.id in existing_order_ids:
                    updated_orders.append(item_order)
                else:
                    new_orders.append(item_order)
                    existing_order_ids.add(item_order.id)

                all_order_ids.append(item_order.id)

            # Insert new orders
            StationOrder.objects.bulk_create(new_orders)

            # Update existing orders
            StationOrder.objects.bulk_update(updated_orders, ['price', 'total_price', 'last_updated', 'volume_remaining'])

            page_number += 1
            break # Read first page for now

        # Delete non-existent orders:
        StationOrder.objects.exclude(
            id__in=all_order_ids,
            station_id=station_id,
        ).delete()

        return True
