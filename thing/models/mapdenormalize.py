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

from thing.models.region import Region
from thing.models.item import Item
from thing.models.constellation import Constellation
from thing.models.system import System
from thing.models.itemgroup import ItemGroup


class MapDenormalize(models.Model):
    item_id = models.IntegerField(unique=True, primary_key=True)
    type = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    group = models.ForeignKey(ItemGroup, on_delete=models.DO_NOTHING)
    solar_system = models.ForeignKey(System, on_delete=models.DO_NOTHING)
    constellation = models.ForeignKey(Constellation, on_delete=models.DO_NOTHING)
    region = models.ForeignKey(Region, on_delete=models.DO_NOTHING)
    orbit_id = models.IntegerField()
    x = models.FloatField()
    y = models.FloatField()
    z = models.FloatField()
    radius = models.FloatField()
    item_name = models.CharField(max_length=8000)
    security = models.FloatField()
    celestial_index = models.IntegerField()
    orbit_index = models.IntegerField()

    class Meta:
        app_label = 'thing'
        ordering = ('item_name'),

    def __unicode__(self):
        return self.item_name
