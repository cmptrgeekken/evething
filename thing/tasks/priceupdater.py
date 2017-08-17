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

from django.db import transaction
from django.db.models import Q


class PriceUpdater(APITask):
    name = 'thing.price_updater'

    def run(self, api_url, taskstate_id, apikey_id, station_or_region_id):
        if self.init(taskstate_id) is False:
            return

        page_number = 1

        stations_query = Station.objects.filter(load_market_orders=True)

        stations = stations_query.filter(id=station_or_region_id, is_citadel=True)
        if len(stations) == 0:
            stations = stations_query.filter(system__constellation__region_id=station_or_region_id, is_citadel=False)

        if len(stations) == 0:
            self.log_warn('No stations found for task: %d!', station_or_region_id)
            return

        primary_station = stations[0]

        station_lookup = set(s.id for s in stations)

        if primary_station is None or primary_station.market_profile is None \
                or primary_station.market_profile.sso_refresh_token is None:
            self.log_warn('No refresh token found for station %d!' % primary_station.id)
            return

        access_token = None
        token_expires = None

        start_time = datetime.now()

        while True:
            if access_token is None or token_expires < datetime.now():
                access_token, token_expires = self.get_access_token(primary_station.market_profile.sso_refresh_token)

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

            station_orders = []
            for order in orders:
                # Ignore stations we're not tracking
                if int(order['location_id']) not in station_lookup:
                    continue

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

                station_orders.append(station_order)

            sql = ""
            for o in station_orders:
                new_sql = "('%s', '%s', '%s', '%s', '%s', '%s', %0.2f, '%d', '%s', '%s', '%s', '%s', '%s'), " \
                       % (str(o.order_id),
                          str(o.item_id),
                          str(o.station_id),
                          str(o.volume_entered),
                          str(o.volume_remaining),
                          str(o.minimum_volume),
                          o.price,
                          o.buy_order,
                          str(o.issued),
                          o.expires,
                          o.range,
                          o.last_updated,
                          str(o.times_updated))

                if len(''.join([sql, new_sql])) > 16777216:
                    self.execute_query(sql)
                    sql = new_sql
                else:
                    sql += new_sql

            sql = sql.rstrip(', ')

            self.execute_query(sql)

            page_number += 1

        # Delete non-existent orders:
        StationOrder.objects.filter(station_id__in=station_ids).exclude(
            last_updated__gte=start_time
        ).delete()

        return True

    @transaction.atomic
    def execute_query(self, sql):
        cursor = self.get_cursor()

        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute(queries.bulk_stationorders_insert_update % sql)
        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()
        self.log_error('Update complete!')

