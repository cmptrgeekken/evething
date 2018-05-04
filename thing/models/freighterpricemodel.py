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
from collections import defaultdict
from thing.models import System, MapDenormalize

import math


class FreighterPriceModel(models.Model):
    name = models.CharField(max_length=32)

    in_system_collateral = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    in_system_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_system_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    in_region_collateral = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    in_region_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_region_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    cross_region_collateral = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    cross_region_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cross_region_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    max_collateral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    ly_origin_system = models.ForeignKey(System, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    ly_base = models.DecimalField(max_digits=10, decimal_places=0)
    ly_collateral = models.DecimalField(max_digits=10, decimal_places=4)

    is_thirdparty = models.BooleanField(default=False)

    sort_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'thing'
        ordering = ('sort_order'),

    def __unicode__(self):
        return self.name

    def calc(self, start_system, end_system, collateral, m3):
        lys = 0
        m3 = min(m3, self.max_m3)
        if self.ly_base is not None and self.ly_base > 0:
            lys = self.calc_ttl_lys(start_system, end_system)
            return (self.calc_ly(lys, collateral), 'Per LY', lys)
        if start_system.id == end_system.id:
            return (self.calc_in_system(collateral, m3), 'Same System', lys)
        elif start_system.constellation.region.id == end_system.constellation.region.id:
            return (self.calc_in_region(collateral, m3), 'Same Region', lys)
        else:
            return (self.calc_cross_region(collateral, m3), 'Cross Region', lys)

    def calc_in_system(self, collateral, m3):
        return self.in_system_base + (collateral * self.in_system_collateral) + (m3 * self.in_system_m3)

    def calc_in_region(self, collateral, m3):
        return self.in_region_base + (collateral * self.in_region_collateral) + (m3 * self.in_region_m3)

    def calc_cross_region(self, collateral, m3):
        return self.cross_region_base + (collateral*self.cross_region_collateral) + (m3*self.cross_region_m3)

    def calc_ly(self, ttl_lys, collateral):
        return ttl_lys * self.ly_base + collateral * self.ly_collateral

    def calc_ttl_lys(self, start_system, end_system):
        return Decimal(self.calc_lys(self.ly_origin_system_id, start_system.id)\
            + self.calc_lys(start_system.id, end_system.id)\
            + self.calc_lys(end_system.id, self.ly_origin_system_id))

    def calc_lys(self, start_system_id, end_system_id):
        start_ref = MapDenormalize.objects.filter(item_id=start_system_id).first()
        end_ref = MapDenormalize.objects.filter(item_id=end_system_id).first()

        return math.sqrt(
            math.pow(start_ref.x - end_ref.x, 2)
            + math.pow(start_ref.y - end_ref.y, 2)
            + math.pow(start_ref.z - end_ref.z, 2)) / 9460730472580800

    def supported_systems(self):
        from thing.models.freightersystem import FreighterSystem

        all_systems = defaultdict(set)

        for fs in FreighterSystem.objects.filter(price_model_id=self.id):
            systems = fs.get_systems()

            for system in systems:
                region = system.constellation.region.name

                all_systems[region].add(system.name)

        return all_systems

    def __unicode__(self):
        return self.name
