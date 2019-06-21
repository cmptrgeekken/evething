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
from thing.models.corporation import Corporation
from thing.models.item import Item


from mptt.models import MPTTModel, TreeForeignKey


class EsiAsset(MPTTModel):
    item_id = models.BigIntegerField(db_index=True)

    character = models.ForeignKey(Character, on_delete=models.DO_NOTHING)
    corporation = models.ForeignKey(Corporation, on_delete=models.DO_NOTHING)

    type = models.ForeignKey(Item, on_delete=models.DO_NOTHING)

    location_flag = models.CharField(max_length=50)
    location_id = models.BigIntegerField()
    location_type = models.CharField(max_length=50)

    asset_name = models.CharField(max_length=128, default='')

    is_singleton = models.BooleanField(default=False)
    is_blueprint_copy = models.BooleanField(default=False)
    quantity = models.IntegerField()

    #location = TreeForeignKey('self', null=True, blank=True, related_name='children', to_field='item_id', db_index=True)

    last_updated = models.DateTimeField()

    class Meta:
        app_label = 'thing'

    class MPTTMeta:
        parent_attr='location_id'
