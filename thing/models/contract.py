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

from thing.models.alliance import Alliance
from thing.models.character import Character
from thing.models.corporation import Corporation
from thing.models.station import Station


class Contract(models.Model):
    character = models.ForeignKey(Character, on_delete=models.DO_NOTHING, null=True)
    corporation = models.ForeignKey(Corporation, blank=True, null=True, on_delete=models.DO_NOTHING)

    contract_id = models.IntegerField(db_index=True)

    issuer_char = models.ForeignKey(Character, blank=True, null=True, related_name='+', on_delete=models.DO_NOTHING)
    issuer_corp = models.ForeignKey(Corporation, related_name='+', on_delete=models.DO_NOTHING)
    assignee_id = models.IntegerField(default=0)
    acceptor_id = models.IntegerField(default=0)

    start_station = models.ForeignKey(Station, blank=True, null=True, related_name='+', on_delete=models.DO_NOTHING)
    end_station = models.ForeignKey(Station, blank=True, null=True, related_name='+', on_delete=models.DO_NOTHING)

    type = models.CharField(max_length=16)
    status = models.CharField(max_length=24)
    title = models.CharField(max_length=64)
    for_corp = models.BooleanField(default=False)
    public = models.BooleanField(default=False)

    date_issued = models.DateTimeField()
    date_expired = models.DateTimeField()
    date_accepted = models.DateTimeField(blank=True, null=True)
    date_completed = models.DateTimeField(blank=True, null=True)
    num_days = models.IntegerField()

    price = models.DecimalField(max_digits=20, decimal_places=2)
    reward = models.DecimalField(max_digits=20, decimal_places=2)
    collateral = models.DecimalField(max_digits=20, decimal_places=2)
    buyout = models.DecimalField(max_digits=20, decimal_places=2)
    volume = models.DecimalField(max_digits=20, decimal_places=4)
    availability = models.CharField(max_length=50)

    retrieved_items = models.BooleanField(default=False)

    class Meta:
        app_label = 'thing'
        ordering = ('-date_issued',)

    def __unicode__(self):
        if self.type == 'Courier':
            return '#%d (%s, %s -> %s)' % (self.contract_id, self.type, self.start_station.short_name, self.end_station.short_name)
        else:
            return '#%d (%s, %s)' % (self.contract_id, self.type, self.start_station.short_name)

    def get_issuer_name(self):
        if self.for_corp:
            return self.issuer_corp.name
        else:
            return self.issuer_char.name

    def get_assignee_name(self):
        alliance = Alliance.objects.filter(id=self.assignee_id).first()

        if alliance is not None and 'Unknown' not in alliance.name:
            return '%s' % alliance.name

        corp = Corporation.objects.filter(id=self.assignee_id).first()
        if corp is not None and 'Unknown' not in corp.name:
            return '%s' % corp.name

        char = Character.objects.filter(id=self.assignee_id).first()
        if char is not None and 'Unknown' not in char.name:
            return '%s' % char.name

        return 'Unknown'

    def get_items(self):
        from thing.models import ContractItem

        items = ContractItem.objects.filter(contract_id=self.id)

        item_lookup = dict()

        for i in items:
            if i.item_id not in item_lookup:
                item_lookup[i.item_id] = i
            else:
                item_lookup[i.item_id].quantity += i.quantity

        return item_lookup.values()
