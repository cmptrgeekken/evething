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

from datetime import datetime
from thing.models import PosWatchPosHistory
from .apitask import APITask


class PosWatch(APITask):
    name = 'thing.poswatch'

    def run(self, url, taskstate_id, apikey_id, character_id):
        if self.init(taskstate_id, apikey_id) is False:
            return

        self._work(url, self.apikey.corporation)

        return True

    # Do the actual work for wallet journal entries
    def _work(self, url, corp):

        self.fetch_api(url)

        pos_entries_query = PosWatchPosHistory.objects.filter(corpId=corp.id)

        for row in self.root.findall('result/rowset/row'):
            stateTimestamp = self.parse_api_date(row.attrib['stateTimestamp'])
            onlineTimestamp = self.parse_api_date(row.attrib['onlineTimestamp'])
            standingOwnerId = int(row.attrib['standingOwnerID'])
            pos_entry = PosWatchPosHistory(
                corpId=corp.id,
                posId=int(row.attrib['itemID']),
                typeId=int(row.attrib['typeID']),
                locationId=int(row.attrib['locationID']),
                moonId=int(row.attrib['moonID']),
                state=int(row.attrib['state']),
                date=datetime.utcnow().date(),
            )

            existing = pos_entries_query.filter(date=pos_entry.date, posId=pos_entry.posId).first()
            if not existing:
                PosWatchPosHistory.objects.insert(pos_entry)
