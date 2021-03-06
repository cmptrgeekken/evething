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

from thing.models import Alliance, Buyback, Corporation


class BuybackLocationGroup(models.Model):
    id = models.IntegerField(primary_key=True)

    buyback = models.ForeignKey(Buyback, on_delete=models.DO_NOTHING)

    name = models.CharField(max_length=100)

    corporation = models.ForeignKey(Corporation, on_delete=models.DO_NOTHING)
    alliance = models.ForeignKey(Alliance, on_delete=models.DO_NOTHING)

    structure_name_filter = models.CharField(max_length=100)

    def get_accepted_locations(self):
        from thing.models.buybacklocation import BuybackLocation

        return BuybackLocation.objects.filter(buyback_location_group_id=self.id, excluded=False)

    def get_excluded_locations(self):
        from thing.models.buybacklocation import BuybackLocation

        return BuybackLocation.objects.filter(buyback_location_group_id=self.id, excluded=True)

    def get_owner(self):
        if self.alliance is not None:
            return "%s (Alliance)" % self.alliance.name

        if self.corporation is not None:
            return "%s (Corporation)" % self.corporation.name

        return "Anyone"

    def get_types(self):
        from thing.models.buybacklocationtype import BuybackLocationType

        return BuybackLocationType.objects.filter(buyback_location_group_id=self.id)
