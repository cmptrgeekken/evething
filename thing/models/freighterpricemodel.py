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

from django.db import models
from collections import defaultdict


class FreighterPriceModel(models.Model):
    name = models.CharField(max_length=32)

    in_system_collateral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_system_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_system_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    in_region_collateral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_region_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    in_region_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    cross_region_collateral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cross_region_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cross_region_base = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    max_collateral = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_m3 = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    is_thirdparty = models.BooleanField(default=False)

    sort_order = models.IntegerField(default=0)

    class Meta:
        app_label = 'thing'
        ordering = ('sort_order'),

    def calc(self, start_system, end_system, collateral, m3):
        if start_system.id == end_system.id:
            return (self.calc_in_system(collateral, m3), 'In System')
        elif start_system.constellation.region.id == end_system.constellation.region.id:
            return (self.calc_in_region(collateral, m3), 'In Region')
        else:
            return (self.calc_cross_region(collateral, m3), 'Cross Region')

    def calc_in_system(self, collateral, m3):
        return self.in_system_base + (collateral * self.in_system_collateral) + (m3 * self.in_system_m3)

    def calc_in_region(self, collateral, m3):
        return self.in_region_base + (collateral * self.in_region_collateral) + (m3 * self.in_region_m3)

    def calc_cross_region(self, collateral, m3):
        return self.cross_region_base + (collateral*self.cross_region_collateral) + (m3*self.cross_region_m3)

    def supported_systems(self):
        from thing.models.freightersystem import FreighterSystem

        all_systems = defaultdict(list)
        for result in FreighterSystem.objects.filter(
            price_model_id=self.id
        ).values('system__constellation__region__name',
                 'system__name').distinct().order_by(
                'system__constellation__region__name', 'system__name'):
            all_systems[result['system__constellation__region__name']].append(result['system__name'])

        return all_systems
    def __unicode__(self):
        return self.name
