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

from thing.models import BuybackLocationGroup, Constellation, Region, Station, System


class BuybackLocation(models.Model):
    id = models.IntegerField(primary_key=True)

    buyback_location_group = models.ForeignKey(BuybackLocationGroup, on_delete=models.DO_NOTHING)
    structure = models.ForeignKey(Station, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    system = models.ForeignKey(System, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    constellation = models.ForeignKey(Constellation, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING, null=True, default=None, blank=True)

    excluded = models.BooleanField()

    def get_name(self):
        if self.region is not None:
            return '%s (Region)' % self.region.name

        if self.constellation is not None:
            return '%s (Constellation)' % self.constellation.name

        if self.system is not None:
            return '%s (%s)' % (self.system.name, self.system.constellation.region.name)

        return '%s (%s)' % (self.structure.name, self.structure.system.constellation.region.name)
