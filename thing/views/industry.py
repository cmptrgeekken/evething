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

from django.conf import settings
from django.contrib.auth.decorators import login_required

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8


@login_required
def industry(request):
    """Industry jobs list"""
    tt = TimerThing('industry')

    cursor = get_cursor()
    cursor.execute(queries.industry_job_slots)
    desc = cursor.description
    current_job_stats = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    stats = {
        'mfg_avail': 0,
        'mfg_deliver': 0,
        'mfg_max': 0,
        'research_avail': 0,
        'research_deliver': 0,
        'research_max': 0,
        'usage': current_job_stats,
    }

    group_stats = {}

    for row in current_job_stats:
        grp = row['group_name']
        stats['mfg_avail'] += row['mfg_slots_avail']
        stats['mfg_max'] += row['mfg_slots_max']
        stats['mfg_deliver'] += row['mfg_slots_deliverable']
        stats['research_avail'] += row['research_slots_avail']
        stats['research_deliver'] += row['research_slots_deliverable']
        stats['research_max'] += row['research_slots_max']

        if grp not in group_stats:
            row['show_group'] = True
            group_stats[grp] = {
                'mfg_avail': 0,
                'mfg_max': 0,
                'mfg_deliver': 0,
                'research_avail': 0,
                'research_deliver': 0,
                'research_max': 0,
            }

        group_stats[grp]['mfg_avail'] += row['mfg_slots_avail']
        group_stats[grp]['mfg_max'] += row['mfg_slots_max']
        group_stats[grp]['mfg_deliver'] += row['mfg_slots_deliverable']
        group_stats[grp]['research_avail'] += row['research_slots_avail']
        group_stats[grp]['research_deliver'] += row['research_slots_deliverable']
        group_stats[grp]['research_max'] += row['research_slots_max']





    # Fetch valid characters/corporations for this user
    characters = Character.objects.filter(
        apikeys__user=request.user,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).distinct()
    character_ids = [c.id for c in characters]

    corporation_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_INDUSTRY_JOBS_MASK)

    tt.add_time('init')

    # Fetch industry jobs for this user
    jobs = IndustryJob.objects.filter(
        Q(character__in=character_ids, corporation=None)
        |
        Q(corporation__in=corporation_ids)
    )
    jobs = jobs.prefetch_related('character', 'corporation', 'system', 'product', 'blueprint')

    # Gather some lookup ids
    char_ids = set()
    station_ids = set()
    for ij in jobs:
        char_ids.add(ij.installer_id)
        station_ids.add(ij.output_location_id)

    # Bulk lookups
    char_map = Character.objects.in_bulk(char_ids)
    station_map = Station.objects.in_bulk(station_ids)

    # Split into incomplete/complete
    utcnow = datetime.datetime.utcnow()

    incomplete = []
    complete = []
    for ij in jobs:
        if ij.end_date < utcnow:
            ij.z_ready = True

        if ij.installer_id in character_ids:
            ij.z_installer_mine = True

        ij.z_installer = char_map.get(ij.installer_id)
        ij.z_station = station_map.get(ij.output_location_id)

        ij.z_datediff = (ij.end_date - utcnow).total_seconds()

        if ij.status == 1:
            incomplete.append(ij)
        else:
            complete.append(ij)

    # Incomplete should be probably sorted in reverse order
    incomplete.sort(key=lambda j: j.end_date)

    tt.add_time('load jobs')

    # Render template
    out = render_page(
        'thing/industry.html',
        {
            'incomplete': incomplete,
            'complete': complete,
            'industry_info': stats,
            'group_stats': group_stats,
        },
        request,
        character_ids,
        corporation_ids,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out
