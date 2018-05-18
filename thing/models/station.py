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

from thing.models.system import System
from thing.models.item import Item
from thing.models.character import Character
from thing.models.corporation import Corporation

numeral_map = zip(
    (1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1),
    ('M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I')
)


def roman_to_int(n):
    n = unicode(n).upper()

    i = result = 0
    for integer, numeral in numeral_map:
        while n[i:i + len(numeral)] == numeral:
            result += integer
            i += len(numeral)
    return result


class Station(models.Model):
    id = models.BigIntegerField(primary_key=True, auto_created=False)
    name = models.CharField(max_length=128)
    short_name = models.CharField(max_length=64, default='')
    is_citadel = models.BooleanField(default=False)
    is_unknown = models.BooleanField(default=False)

    load_market_orders = models.BooleanField(default=False)
    market_profile = models.ForeignKey(Character, null=True, default=None, on_delete=models.DO_NOTHING)

    system = models.ForeignKey(System, blank=True, null=True, default=None, on_delete=models.DO_NOTHING)
    type = models.ForeignKey(Item, null=True, default=None, on_delete=models.DO_NOTHING)
    corporation = models.ForeignKey(Corporation, null=True, default=None, on_delete=models.DO_NOTHING)

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name

    def get_system_name(self):
        return self.system.name if self.system is not None else "[Unknown]"

    def get_display_name(self):
        return self.short_name if self.short_name else self.name

    # Build the short name when this object is saved
    def save(self, *args, **kwargs):
        self._make_shorter_name()
        if self.system_id == 0:
            self.system_id = None
        if self.market_profile_id == 0:
            self.market_profile_id = None

        super(Station, self).save(*args, **kwargs)

    def _make_shorter_name(self):
        out = []

        parts = self.name.split(' - ')
        if len(parts) == 1:
            self.short_name = self.name
        else:
            a_parts = parts[0].split()
            if len(a_parts) > 1:
                # Change the roman annoyance to a proper digit
                out.append('%s %s' % (a_parts[0], str(roman_to_int(a_parts[1]))))
                # Moooon
                if parts[1].startswith('Moon') and len(parts) == 3:
                    out[0] = '%s-%s' % (out[0], parts[1][5:])
                    out.append(''.join(s[0] for s in parts[2].split()))
                else:
                    out.append(''.join(s[0] for s in parts[1].split()))
            else:
                out.append(a_parts[0])

            self.short_name = ' - '.join(out)
