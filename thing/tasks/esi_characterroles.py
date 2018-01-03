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

import datetime

from .apitask import APITask
import json

from thing.models import CharacterApiScope, CharacterApiRole


class EsiCharacterRoles(APITask):
    name = 'thing.characterroles'

    roles_url = 'https://esi.tech.ccp.is/latest/characters/%s/roles/?datasource=tranquility'

    def run(self, character_id=None):
        self.init()

        roles_scopes = CharacterApiScope.objects.filter(scope='esi-characters.read_corporation_roles.v1')

        if character_id is not None:
            roles_scopes = roles_scopes.filter(character_id=character_id)

        for scope in roles_scopes:
            self.update_roles(scope.character)

    def update_roles(self, character):
        refresh_token = character.sso_refresh_token

        access_token, expires = self.get_access_token(refresh_token)

        results = self.fetch_esi_url(self.roles_url % character.id, access_token)

        info = None

        try:
            info = json.loads(results)
        except:
            self.log_debug("Cannot find roles for: %s" % character.id)

        if info is None:
            return False

        CharacterApiRole.objects.filter(character_id=character.id).exclude(role__in=info['roles']).delete()

        current_roles = CharacterApiRole.objects.filter(character_id=character.id)

        current_roles_lookup = dict()
        for r in current_roles:
            current_roles_lookup[r.role] = r

        for role in info['roles']:
            if role not in current_roles_lookup:
                role = CharacterApiRole(
                    character_id=character.id,
                    role=role,
                )

                role.save()

        return True
