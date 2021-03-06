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

from thing.models.character import Character
from thing.models.item import Item
from thing.models.implant import Implant


class CharacterDetails(models.Model):
    """Character details"""
    character = models.OneToOneField(
        Character, unique=True, primary_key=True, related_name='details'
    )

    wallet_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )

    cha_attribute = models.SmallIntegerField(default=20)
    int_attribute = models.SmallIntegerField(default=20)
    mem_attribute = models.SmallIntegerField(default=20)
    per_attribute = models.SmallIntegerField(default=20)
    wil_attribute = models.SmallIntegerField(default=19)

    __attr_bonus = {}

    def __get_attr_bonus(self, attr):
        if not self.__attr_bonus:
            self.__attr_bonus = self.implants.all().aggregate(
                models.Sum('charisma_modifier'),
                models.Sum('intelligence_modifier'),
                models.Sum('memory_modifier'),
                models.Sum('perception_modifier'),
                models.Sum('willpower_modifier')
            )
        return self.__attr_bonus[attr + '_modifier__sum'] if \
            self.__attr_bonus[attr + '_modifier__sum'] else 0

    @property
    def cha_bonus(self):
        return self.__get_attr_bonus('charisma')

    @property
    def int_bonus(self):
        return self.__get_attr_bonus('intelligence')

    @property
    def mem_bonus(self):
        return self.__get_attr_bonus('memory')

    @property
    def per_bonus(self):
        return self.__get_attr_bonus('perception')

    @property
    def wil_bonus(self):
        return self.__get_attr_bonus('willpower')

    implants = models.ManyToManyField(Implant)

    security_status = models.DecimalField(
        max_digits=6, decimal_places=4, default=0
    )

    last_known_location = models.CharField(max_length=255, default='')
    ship_item = models.ForeignKey(Item, blank=True, null=True, on_delete=models.DO_NOTHING)
    ship_name = models.CharField(max_length=128, default='')

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return '%s' % self.character
