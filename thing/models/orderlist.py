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

from decimal import Decimal

from django.db import models
from django.db.models import Sum, F

from thing.models.itemgroup import ItemGroup
from thing.models.marketgroup import MarketGroup
from thing import queries


class OrderList:
    def __init__(self, item_id, item_name, station_id, station_name, buy_tolerance=None):
        self.item_id = item_id
        self.item_name = item_name
        self.station_id = station_id
        self.station_name = station_name

        if buy_tolerance is not None:
            self.buy_tolerance = buy_tolerance

        self.orders = []

        self.max_price = 0
        self.total_price_best = 0
        self.total_price_multibuy = 0
        self.total_price_with_shipping = 0
        self.total_volume = 0
        self.total_shipping = 0
        self.total_quantity = 0
        self.multibuy_ok = True
        self.last_updated = None

    def add_order(self, order):
        self.orders.append(order)

        self.total_price_best += order.z_order_qty * order.price
        self.total_quantity += order.z_order_qty
        self.total_volume += order.z_order_qty * order.item.volume
        self.total_shipping += order.shipping * order.z_order_qty
        self.total_price_with_shipping += order.price_with_shipping * order.z_order_qty

        self.last_updated = order.last_updated if self.last_updated is None else max(self.last_updated, order.last_updated)

        if self.max_price < order.price:
            self.max_price = order.price

            self.total_price_multibuy = self.max_price * self.total_quantity

        if self.total_price_multibuy * Decimal(1-self.buy_tolerance) > self.total_price_best:
            self.multibuy_ok = False
