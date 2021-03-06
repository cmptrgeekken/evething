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
from thing import queries

from django.db import transaction


class PriceUpdater(APITask):
    name = 'thing.price_updater'

    def run(self, a=None, b=None, c=None, d=None):
        self.init()

        stations = Station.objects.filter(load_market_orders=True).select_related('market_profile')

        order_regions = set()
        for station in stations:
            if station.is_citadel:
                url = 'https://esi.evetech.net/latest/markets/structures/%d?datasource=tranquility&page=' \
                      % station.id
            else:
                region_id = station.system.constellation.region.id
                order_regions.add(region_id)
                continue

            self.import_prices(url, station.id)

        for region_id in order_regions:
            url = 'https://esi.evetech.net/latest/markets/%d/orders?datasource=tranquility&order_type=all&page=' \
                  % region_id
            self.import_prices(url, region_id)

    def import_prices(self, api_url, station_or_region_id):
        page_number = 1

        stations_query = Station.objects.filter(load_market_orders=True)

        stations = stations_query.filter(id=station_or_region_id, is_citadel=True)
        if len(stations) == 0:
            stations = stations_query.filter(system__constellation__region_id=station_or_region_id, is_citadel=False)

        if len(stations) == 0:
            self.log_error('No stations found for task: %d!', station_or_region_id)
            return False

        primary_station = stations[0]

        station_lookup = set(s.id for s in stations)

        if primary_station is None or primary_station.market_profile is None \
                or primary_station.market_profile.sso_refresh_token is None:
            self.log_error('No refresh token found for station %d!' % primary_station.id)
            return False

        self.log_info('Importing data for station %s...' % primary_station.name)

        start_time = datetime.now()

        initial_url = api_url + str(page_number)
        success, data, headers = self.fetch_esi_url(initial_url, primary_station.market_profile, headers_to_return=['x-pages'])
        if not success:
            self.log_error("Station %s error: %s" % (primary_station.name, data))
            return

        max_pages = int(headers['x-pages'])

        urls = [api_url + str(i) for i in range(2, max_pages+1)]

        if max_pages > 1:
            all_station_data = self.fetch_batch_esi_urls(urls, primary_station.market_profile, batch_size=20)
        else:
            all_station_data = dict()

        self.log_debug('Fetched %d URLs in %d seconds' % (len(urls)+1, (datetime.now()-start_time).total_seconds()))

        all_station_data[initial_url] = (success, data)

        total_orders = 0

        cursor = self.get_cursor()

        cursor.execute(queries.bulk_stationorder_drop_tmp)
        cursor.execute(queries.bulk_stationorder_create_tmp)

        seen_ids = set()

        sql_inserts = []
        for url, station_data in all_station_data.items():
            success, data = station_data

            if not success:
                self.log_error('API returned an error for url %s' % url)
                return False

            try:
                orders = json.loads(data)
            except:
                return False

            if len(orders) == 0:
                return False

            total_orders += len(orders)

            for order in orders:
                # Ignore stations we're not tracking
                if int(order['location_id']) not in station_lookup:
                    continue

                # Create the new order object
                remaining = int(order['volume_remain'])
                price = Decimal(order['price'])
                issued = self.parse_api_date(order['issued'], True)

                order_id = int(order['order_id'])
                item_id = int(order['type_id'])
                station_id = int(order['location_id'])
                buy_order = order['is_buy_order']
                volume_entered = int(order['volume_total'])
                volume_remaining = remaining
                minimum_volume = int(order['min_volume'])
                expires = issued + timedelta(int(order['duration']))
                order_range = order['range']
                times_updated = 1
                last_updated = start_time

                if order_id in seen_ids:
                    continue

                seen_ids.add(order_id)

                new_sql = "(%d, %d, %d, '%d', '%d', '%d', %0.2f, '%d', '%s', '%s', '%s', '%s', %d)" \
                          % (order_id,
                             item_id,
                             station_id,
                             volume_entered,
                             volume_remaining,
                             minimum_volume,
                             price,
                             buy_order,
                             issued,
                             expires,
                             order_range,
                             last_updated,
                             times_updated)

                sql_inserts.append(new_sql)

                if len(sql_inserts) >= 10000:
                    #self.log_debug('Inserting %d records...%s' % (len(sql_inserts), datetime.now()))
                    self.execute_query(sql_inserts)
                    sql_inserts = []

        self.log_info('Finished importing data for %s' % primary_station.name)

        #self.log_debug('Inserting %d records...%s' % (len(sql_inserts), datetime.now()))
        self.execute_query(sql_inserts)

        #self.log_debug('Deleting old orders...%s' % datetime.now())
        cursor.execute(queries.bulk_stationorder_delete % ','.join(str(x) for x in station_lookup))
        #self.log_debug('Updating orders...%s' % datetime.now())
        cursor.execute(queries.bulk_stationorder_update)
        #self.log_debug('Inserting new orders...%s' % datetime.now())
        cursor.execute(queries.bulk_stationorder_insert)


        # Update market orders
        cursor = self.get_cursor()
        #self.log_debug('Updating market orders..%s' % datetime.now())
        #cursor.execute(queries.order_updatemarketorders)
        cursor.close()

        #self.log_debug('Finished after %d seconds' % (datetime.now()-start_time).total_seconds())

        return True

    @transaction.atomic
    def execute_query(self, sql_inserts):
        cursor = self.get_cursor()

        order_ct = len(sql_inserts)

        if order_ct == 0:
            return

        sql = ','.join(sql_inserts)

        cursor.execute('SET autocommit=0')
        cursor.execute('SET unique_checks=0')
        cursor.execute('SET foreign_key_checks=0')
        cursor.execute(queries.bulk_stationorder_tmp_insert % sql)
        cursor.execute('SET foreign_key_checks=1')
        cursor.execute('SET unique_checks=1')
        cursor.execute('SET autocommit=1')
        transaction.set_dirty()
        

