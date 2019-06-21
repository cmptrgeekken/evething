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
from django.db.models import Sum

from thing.models import corporation


class Character(models.Model):
    id = models.IntegerField(primary_key=True)

    name = models.CharField(max_length=64)
    corporation = models.ForeignKey(corporation.Corporation, blank=True, null=True, on_delete=models.DO_NOTHING)
    sso_refresh_token = models.CharField(max_length=4000)
    sso_error_count = models.IntegerField(default=0)
    not_found = models.BooleanField(default=False)


    class Meta:
        app_label = 'thing'
        ordering = ('name',)

    def __init__(self, *args, **kwargs):
        super(Character, self).__init__(*args, **kwargs)
        self.sso_access_token = None
        self.sso_token_expires = None

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('character', (), {'character_name': self.name, })

    def get_total_skill_points(self):
        from thing.models.characterskill import CharacterSkill
        return CharacterSkill.objects.filter(character=self).aggregate(total_sp=Sum('points'))['total_sp']

    def get_scopes(self):
        from thing.models.characterapiscope import CharacterApiScope

        return set([s.scope for s in CharacterApiScope.objects.filter(character_id=self.id)])

    def get_apiroles(self):
        from thing.models.characterapirole import CharacterApiRole

        return set([r.role for r in CharacterApiRole.objects.filter(character_id=self.id)])

    def deauthorize_user(self):
        from thing.models import CharacterApiScope, CharacterApiRole
        CharacterApiScope.objects.filter(character_id=self.id).delete()
        CharacterApiRole.objects.filter(character_id=self.id).delete()
        self.sso_refresh_token = None
        self.save()
