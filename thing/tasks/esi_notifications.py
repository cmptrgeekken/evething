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

from thing.models import CharacterApiScope, Character, Notification, MoonExtractionHistory, Structure, MoonConfig
import re

from thing.filetimes import filetime_to_dt, dt_to_filetime

class EsiNotifications(APITask):
    name = 'thing.esi_notifications'

    notifications_url = 'https://esi.evetech.net/latest/characters/%s/notifications/?datasource=tranquility'

    def run(self, character_id=None):
        self.init()

        notification_scopes = CharacterApiScope.objects.filter(scope='esi-characters.read_notifications.v1')

        if character_id is not None:
            notification_scopes = notification_scopes.filter(character_id=character_id)

        for scope in notification_scopes:
            try:
               self.import_notifications(scope.character)
            except:
                continue

    def import_notifications(self, character):
        success, results = self.fetch_esi_url(self.notifications_url % character.id, character)

        if not success:
            return

        info = None

        try:
            info = json.loads(results)
        except:
            self.log_debug("Cannot import notifications for: %s" % character.id)

        if info is None:
            return False

        char_notifications = Notification.objects.filter(character_id=character.id)

        for n in info:

            db_notify = char_notifications.filter(notification_id=n['notification_id']).first()

            if not db_notify:
                notification = Notification(
                    notification_id=n['notification_id'],
                    character_id=character.id,
                    type=n['type'],
                    sender_id=n['sender_id'],
                    sender_type=n['sender_type'],
                    timestamp=self.parse_api_date(n['timestamp'], True),
                    is_read='is_read' in n and n['is_read'],
                    text=n['text'],
                )

                notification.save()

                self.handle_notification(notification)

        return True

    def update_moon_comp(self, lookup, structure):
        cfg = MoonConfig.objects.filter(structure_id=structure.id).first()

        if cfg is None:
            cfg = MoonConfig(structure_id=structure.id)

        ores = list()
        ttl_m3 = float(0)

        for key in lookup.keys():
            if key.isdigit():
            	ores.append(dict(id=key, m3=float(lookup[key])))
                ttl_m3 += float(lookup[key])

        if len(ores) > 0:
            cfg.first_ore_id = ores[0]['id']
            cfg.first_ore_pct = ores[0]['m3'] / ttl_m3

        if len(ores) > 1:
            cfg.second_ore_id = ores[1]['id']
            cfg.second_ore_pct = ores[1]['m3'] / ttl_m3
        else:
            cfg.second_ore_id = None
            cfg.second_ore_pct = None

        if len(ores) > 2:
            cfg.third_ore_id = ores[2]['id']
            cfg.third_ore_pct = ores[2]['m3'] / ttl_m3
        else:
            cfg.third_ore_id = None
            cfg.third_ore_pct = None
         
        if len(ores) > 3:
            cfg.fourth_ore_id = ores[3]['id']
            cfg.fourth_ore_pct = ores[3]['m3'] / ttl_m3
        else:
            cfg.fourth_ore_id = None
            cfg.fourth_ore_pct = None

        if cfg.first_ore_id is not None:
            cfg.save()



    def handle_notification(self, n):
        lookup = dict()

        lines = n.text.split('\n')
        for l in lines:
            kvp = l.split(': ')

            if len(kvp) == 2:
                lookup[kvp[0].strip()] = kvp[1].strip()

        if n.type == 'MoonminingExtractionFinished':
            """
autoTime: 131616468600000000
moonID: 40130478
moonLink: <a href=\"showinfo:14//40130478\">Y-C3EQ II - Moon 2</a>
oreVolumeByType:
  45511: 4389888.60245198
  45513: 3505947.5336502
  46677: 2458297.820703934
  46685: 3050349.576269587
solarSystemID: 30002044
solarSystemLink: <a href=\"showinfo:5//30002044\">Y-C3EQ</a>
structureID: 1025865354721
structureLink: <a href=\"showinfo:35835//1025865354721\">Y-C3EQ - DRILL R64 P2M2</a>
structureName: Y-C3EQ - DRILL R64 P2M2
structureTypeID: 35835

            """

            structure = Structure.objects.filter(station_id=lookup['structureID']).first()

            if structure is not None:
                self.update_moon_comp(lookup, structure)

            return
        elif n.type == 'MoonminingLaserFired':
            """
firedBy: 826639820
firedByLink: <a href=\"showinfo:1375//826639820\">Nidia Masters</a>
moonID: 40129944
moonLink: <a href=\"showinfo:14//40129944\">D2-HOS IV - Moon 5</a>
oreVolumeByType:
  45504: 3942922.440780203
  45511: 2866507.7126443386
  45512: 2754761.2387239933
  46683: 3868841.941184799
solarSystemID: 30002036
solarSystemLink: <a href=\"showinfo:5//30002036\">D2-HOS</a>
structureID: 1025865069157
structureLink: <a href=\"showinfo:35835//1025865069157\">D2-HOS - DRILL R64 P4M5 Refinery</a>
structureName: D2-HOS - DRILL R64 P4M5 Refinery
structureTypeID: 35835

            """

            structure = Structure.objects.filter(station_id=lookup['structureID']).first()

            if structure is not None:
                self.update_moon_comp(lookup, structure)

            history = MoonExtractionHistory.objects.filter(structure_id=lookup['structureID'], chunk_arrival_time__lte=n.timestamp).order_by('-chunk_arrival_time').first()

            if history is not None:
                char = Character.objects.filter(id=lookup['firedBy']).first()
                if char is None:
                    char = Character(
                        id=lookup['firedBy'],
                        name='*UNKNOWN*',
                    )
                    char.save()

                history.laser_fire_time = n.timestamp
                history.laser_fired_by_id = lookup['firedBy']

                history.save()

            return
        elif n.type == 'MoonminingExtractionStarted' or n.type == 'notificationTypeMoonminingExtractionStarted':
            """
autoTime: 131639472599604532
moonID: 40130188
moonLink: <a href=\"showinfo:14//40130188\">HPS5-C IV - Moon 1</a>
oreVolumeByType:
  45511: 2856681.291149722
  46677: 2876431.0361411837
  46680: 5800457.368840774
  46685: 1597874.5526389943
readyTime: 131639364599604532
solarSystemID: 30002040
solarSystemLink: <a href=\"showinfo:5//30002040\">HPS5-C</a>
startedBy: 826639820
startedByLink: <a href=\"showinfo:1375//826639820\">Nidia Masters</a>
structureID: 1025921067683
structureLink: <a href=\"showinfo:35835//1025921067683\">HPS5-C - DRILL R64 P4M1 Refinery</a>
structureName: HPS5-C - DRILL R64 P4M1 Refinery
structureTypeID: 35835
            """
            structure = Structure.objects.filter(station_id=lookup['structureID']).first()

            if structure is not None:
		self.update_moon_comp(lookup, structure)

            natural_decay_time = filetime_to_dt(int(lookup['autoTime']))
            chunk_arrival_time = filetime_to_dt(int(lookup['readyTime']))

            history = MoonExtractionHistory.objects.filter(structure_id=lookup['structureID'], chunk_arrival_time__lte=n.timestamp+datetime.timedelta(minutes=10), chunk_arrival_time__gte=n.timestamp-datetime.timedelta(minutes=10)).order_by('-chunk_arrival_time').first()

            if history is None:
                history = MoonExtractionHistory(
                    structure_id=lookup['structureID'],
                    moon_id=lookup['moonID'],
                    extraction_start_time=n.timestamp,
                    chunk_arrival_time=chunk_arrival_time,
                    natural_decay_time=natural_decay_time,
                    chunk_minutes=(chunk_arrival_time-n.timestamp).total_seconds()/60.0
                )

            if history is not None:
                char = Character.objects.filter(id=lookup['startedBy']).first()
                if char is None:
                    char = Character(
                        id=lookup['startedBy'],
                        name='*UNKNOWN*',
                    )
                    char.save()

                history.extraction_started_by_id = lookup['startedBy']

                history.save()

            return
        elif n.type == 'MoonminingAutomaticFracture':
            """
moonID: 40234111
moonLink: <a href=\"showinfo:14//40234111\">8W-OSE VII - Moon 3</a>
oreVolumeByType:
  45513: 9280897.862146297
  46681: 5484816.337259444
  46683: 11206724.689483145
solarSystemID: 30003695
solarSystemLink: <a href=\"showinfo:5//30003695\">8W-OSE</a>
structureID: 1025921596673
structureLink: <a href=\"showinfo:35835//1025921596673\">8W-OSE - DRILL N64 P7M3</a>
structureName: 8W-OSE - DRILL N64 P7M3
structureTypeID: 35835

            """

            history = MoonExtractionHistory.objects.filter(structure_id=lookup['structureID'], natural_decay_time__lte=n.timestamp).order_by('-chunk_arrival_time').first()

            if history is not None:
                history.laser_fire_time = n.timestamp
                history.save()

            return
        elif n.type == 'MoonminingExtractionCancelled':
            """
cancelledBy: 826639820
cancelledByLink: <a href=\"showinfo:1375//826639820\">Nidia Masters</a>
moonID: 40128743
moonLink: <a href=\"showinfo:14//40128743\">ZKYV-W VI - Moon 3</a>
solarSystemID: 30002018
solarSystemLink: <a href=\"showinfo:5//30002018\">ZKYV-W</a>
structureID: 1025865174905
structureLink: <a href=\"showinfo:35835//1025865174905\">ZKYV-W - DRILL R64 P6M3 Refinery</a>
structureName: ZKYV-W - DRILL R64 P6M3 Refinery
structureTypeID: 35835
            """
            return
