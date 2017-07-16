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
from thing.models import Station, StationOrder, StationOrderUpdater
from thing import queries


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

        existing_orders = StationOrder.objects.filter(
            station_id=station_id
        ).values_list('order_id')

        access_token = None
        token_expires = None

        existing_order_ids = set([o[0] for o in existing_orders])

        start_time = datetime.now()

        while True:
            if access_token is None or token_expires < datetime.now():
                access_token, token_expires = self.get_access_token(station.market_profile.sso_refresh_token)

            # Retrieve market data and parse the JSON
            url = api_url + str(page_number)
            data = self.fetch_esi_url(url, access_token)
            if data is False:
                continue

            try:
                orders = json.loads(data)
            except:
                break

            if len(orders) == 0:
                break

            new_orders = dict()
            updated_orders = {}
            updated_order_map = {}
            current_order_ids = []
            for order in orders:
                # Create the new order object
                remaining = int(order['volume_remain'])
                price = Decimal(order['price'])
                issued = self.parse_api_date(order['issued'], True)

                station_order = StationOrder(
                    order_id=int(order['order_id']),
                    item_id=int(order['type_id']),
                    station_id=int(order['location_id']),
                    price=price,
                    buy_order=order['is_buy_order'],
                    volume_entered=int(order['volume_total']),
                    volume_remaining=remaining,
                    minimum_volume=int(order['min_volume']),
                    issued=issued,
                    expires=issued + timedelta(int(order['duration'])),
                    range=order['range'],
                    times_updated=1,
                    last_updated=start_time,
                )

                order_updater = StationOrderUpdater(
                    order_id=station_order.order_id,
                    price=station_order.price,
                    volume_remaining=station_order.volume_remaining,
                    station_id=station_id,
                )

                # Ignore stations we're not tracking
                if int(order['location_id']) != int(station_id):
                    continue

                if station_order.order_id in existing_order_ids:
                    updated_orders[station_order.order_id] = order_updater
                    updated_order_map[station_order.order_id] = station_order
                    current_order_ids.append(station_order.order_id)
                else:
                    existing_order_ids.add(station_order.order_id)
                    if station_order.order_id not in new_orders:
                        new_orders[station_order.order_id] = station_order

            # Insert new orders
            StationOrder.objects.bulk_create(new_orders.items())

            # Attempt at more-efficient bulk updates
            if len(updated_orders) > 0:
                StationOrderUpdater.objects.filter(order_id__in=current_order_ids).delete()
                StationOrderUpdater.objects.bulk_create(updated_orders.values())

                cursor = self.get_cursor()
                cursor.execute(queries.stationorder_ids_to_update)
                order_ids = set([col[0] for col in cursor.fetchall()])

                for id in order_ids:
                    if id in updated_order_map:
                        order_update = updated_orders[id]
                        order = updated_order_map[id]
                        order.times_updated += 1
                        order.price = order_update.price
                        order.volume_remaining = order_update.volume_remaining
                        order.save()

            StationOrder.objects.filter(order_id__in=current_order_ids).update(last_updated=start_time)

            page_number += 1

        # Delete non-existent orders:
        StationOrder.objects.filter(station_id=station_id).exclude(
            last_updated__gte=start_time
        ).delete()

        # Delete all StationOrderUpdater entries for this station
        StationOrderUpdater.objects.filter(station_id=station_id).delete()

        return True
