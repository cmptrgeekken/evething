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
import operator
from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.db import connections

from thing import queries

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8
from thing.templatetags.thing_extras import shortduration

ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY


def index(request):
    return stats(request)

    #"""Index page"""
    #tt = TimerThing('index')

    # profile = request.user.profile

    #tt.add_time('profile')

    # Render template
    #out = render_page(
    #    'pgsus/index.html',
    #    {
    #        'profile': 'hello!'
    #    },
    #    request,
    #)

    #tt.add_time('template')
    #if settings.DEBUG:
    #    tt.finished()

    #return out

def stats(request):

    fuel_purchase_stats = dictfetchall(queries.fuelblock_purchase_stats)
    fuel_pending_stats = dictfetchall(queries.fuelblock_pending_stats)
    fuel_job_stats = dictfetchall(queries.fuelblock_job_stats)
    courier_completed_stats = dictfetchall(queries.courier_completed_stats)
    courier_pending_stats = dictfetchall(queries.courier_pending_stats)
    buyback_completed_stats = dictfetchall(queries.buyback_completed_stats)
    buyback_pending_stats = dictfetchall(queries.buyback_pending_stats)

    out = render_page(
        'pgsus/stats.html',
        dict(
            fuel_purchase_stats=fuel_purchase_stats,
            fuel_pending_stats=fuel_pending_stats,
            fuel_job_stats=fuel_job_stats,
            courier_completed_stats=courier_completed_stats[0],
            courier_pending_stats=courier_pending_stats[0],
            buyback_completed_stats=buyback_completed_stats[0],
            buyback_pending_stats=buyback_pending_stats[0],
        ),
        request,
    )

    return out

def get_cursor(db='default'):
    return connections[db].cursor()

def dictfetchall(query):
    "Returns all rows from a cursor as a dict"
    cursor = get_cursor()
    cursor.execute(query)
    desc = cursor.description
    results = [
            dict(zip([col[0] for col in desc], row))
            for row in cursor.fetchall()
    ]

    cursor.close()

    return results