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

from thing.models.freighterpricemodel import FreighterPriceModel
from thing.models.system import System
from thing.models.constellation import Constellation
from thing.models.region import Region


class FreighterSystem(models.Model):
    price_model = models.ForeignKey(FreighterPriceModel, on_delete=models.DO_NOTHING)
    system = models.ForeignKey(System, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    constellation = models.ForeignKey(Constellation, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    excluded = models.BooleanField()

    class Meta:
        app_label = 'thing'
        ordering = ('system__name',)

    def get_systems(self):
        if self.system_id is not None:
            return System.objects.filter(id=self.system_id)
        elif self.constellation_id is not None:
            return System.objects.filter(constellation_id=self.constellation_id)
        elif self.region_id is not None:
            return System.objects.filter(constellation__region_id=self.region_id)

    def __unicode__(self):
        if self.system_id is not None:
            return self.system.name
        elif self.constellation_id is not None:
            return self.constellation.name
        elif self.region_id is not None:
            return self.region.name
        return 'Unknown'
