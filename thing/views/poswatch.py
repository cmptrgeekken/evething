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
def poswatch(request):
    """Industry jobs list"""
    tt = TimerThing('industry')

    cursor = get_cursor()
    cursor.execute(queries.poswatch_taxman)
    desc = cursor.description
    outstanding_tax_info = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    cursor = get_cursor()
    cursor.execute(queries.poswatch_taxman_all)
    desc = cursor.description
    all_tax_info = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    total_outstanding = sum([t['tax_remaining'] for t in outstanding_tax_info])
    total_paid = sum([t['tax_paid'] for t in all_tax_info])
    total_towers = sum([t['last_tower_count'] for t in all_tax_info])

    # Render template
    out = render_page(
        'thing/poswatch.html',
        {
            'outstanding_tax_info': outstanding_tax_info,
            'all_tax_info': all_tax_info,
            'total_outstanding': total_outstanding,
            'total_paid': total_paid,
            'total_towers': total_towers,
        },
        request
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

def poses(request):
    corp_id = request.GET['id']

    poses = PosWatchPosHistory.objects.filter(corp_id=corp_id)

    out = render_page(
        'thing/poses.html',
        {
            poses,
        },
        request
    )

    return out

