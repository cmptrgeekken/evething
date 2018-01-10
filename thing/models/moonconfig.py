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

from thing.models.structure import Structure
from thing.models.item import Item


class MoonConfig(models.Model):
    structure = models.ForeignKey(Structure, on_delete=models.DO_NOTHING, unique=True)
    chunk_days = models.IntegerField(default=28)
    next_date_override = models.DateTimeField()
    is_nationalized = models.BooleanField(default=False)
    ignore_refire = models.BooleanField(default=False)

    first_ore = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='first_ore_id')
    first_ore_pct = models.DecimalField(decimal_places=2, max_digits=2)

    second_ore = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='second_ore_id')
    second_ore_pct = models.DecimalField(decimal_places=2, max_digits=2)

    third_ore = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='third_ore_id')
    third_ore_pct = models.DecimalField(decimal_places=2, max_digits=2)

    fourth_ore = models.ForeignKey(Item, on_delete=models.DO_NOTHING, related_name='fourth_ore_id')
    fourth_ore_pct = models.DecimalField(decimal_places=2, max_digits=2)

    last_chunk_time = models.DateTimeField(null=True)
    last_chunk_minutes = models.IntegerField(null=True)


    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.structure.name

    def get_composition(self):
        try:
            comp = "<ul><li>%s</li><li>%s</li>" % (self.first_ore.get_ore_display(self.first_ore_pct), self.second_ore.get_ore_display(self.second_ore_pct))
            try:
                comp += "<li>%s</li>" % (self.third_ore.get_ore_display(self.third_ore_pct))
            except:
                pass

            try:
                comp += "<li>%s</li>" % (self.fourth_ore.get_ore_display(self.fourth_ore_pct))
            except:
                pass
            comp += "</ul>"
        except:
            comp = "** UNKNOWN **"

        return comp


