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

from thing.models import CharacterApiScope, EsiAsset, MoonExtraction, Station, Structure, StructureService
from thing import queries
from thing.utils import dictfetchall

import traceback


class EsiAssets(APITask):
    name = 'thing.esiassets'

    char_asset_url = 'https://esi.tech.ccp.is/latest/characters/%s/assets/?datasource=tranquility&page=%d'
    corp_asset_url = 'https://esi.tech.ccp.is/latest/corporations/%s/assets/?datasource=tranquility&page=%d'

    def run(self, base_url):
        self.init()

        char_asset_scopes = CharacterApiScope.objects.filter(scope='esi-assets.read_assets.v1')
        corp_asset_scopes = CharacterApiScope.objects.filter(scope='esi-assets.read_corporation_assets.v1')

        for scope in char_asset_scopes:
            self.import_assets(scope.character, False)

        for scope in corp_asset_scopes:
            self.import_assets(scope.character, True)

    def import_assets(self, character, is_corporation):
        char_id = character.id
        corp_id = character.corporation.id

        page = 1
        try:
            while True:
                if is_corporation:
                    success, results = self.fetch_esi_url(self.corp_asset_url % (corp_id, page), character)
                else:
                    success, results = self.fetch_esi_url(self.char_asset_url % (char_id, page), character)

                if not success:
                    break
                page += 1
                asset_info = json.loads(results)

                if len(asset_info) == 0:
                    break

                for asset in asset_info:
                    """
                      {
                        "type_id": 27127,
                        "location_id": 60015106,
                        "location_type": "station",
                        "item_id": 1021659191288,
                        "location_flag": "Hangar",
                        "is_singleton": false,
                        "quantity": 1
                      }
                    """

                    db_asset = EsiAsset.objects.filter(item_id=asset['item_id']).first()
                    if db_asset is None:
                        db_asset = EsiAsset(
                            item_id=asset['item_id'],
                            type_id=asset['type_id'],
                        )

                    db_asset.location_id = asset['location_id']
                    db_asset.location_type = asset['location_type']
                    db_asset.location_flag = asset['location_flag']
                    db_asset.is_singleton = asset['is_singleton']
                    if 'quantity' in asset:
                        db_asset.quantity = asset['quantity']
                    else:
                        db_asset.quantity = 1

                    if is_corporation:
                        db_asset.corporation_id = corp_id
                        db_asset.character_id = None
                    else:
                        db_asset.character_id = char_id
                        db_asset.corporation_id = None

                    db_asset.last_updated = datetime.datetime.now()

                    db_asset.save()
        except Exception, e:
            traceback.print_exc(e)
            return True

        to_delete = EsiAsset.objects.filter(last_updated__lt=datetime.datetime.now() - datetime.timedelta(hours=1))

        if is_corporation:
            to_delete = to_delete.filter(corporation_id=corp_id)
        else:
            to_delete = to_delete.filter(character_id=char_id)

        to_delete.delete()

        return True
