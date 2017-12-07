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
import time
from urllib import urlencode

from django.core.cache import cache
from django.db.models import Count, Q
from django.db import connections
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings

from requests_oauth2 import OAuth2

from thing import queries
from thing.utils import ApiHelper


def render_page(template, data, request, character_ids=None, corporation_ids=None):
    """Wrapper around render_to_response"""
    from thing.models import APIKey, Character, Corporation, Contract, IndustryJob, MailMessage, TaskState

    utcnow = datetime.datetime.utcnow()

    data['server_open'] = cache.get('server_open')
    data['online_players'] = cache.get('online_players')
    data['ga_tracking_code'] = getattr(settings, 'GA_TRACKING_CODE', None)

    if 'char' in request.session:
        data['charid'] = request.session['char']['id']
        data['charname'] = request.session['char']['name']

    api_helper = ApiHelper()

    oauth2_handler = api_helper.oauth_handler()

    data['oauth_authorize_url'] = oauth2_handler.authorize_url(
        '',
        response_type='code',
        state='client_authorize')

    data['oauth_authorize_ui_url'] = oauth2_handler.authorize_url(
        'esi-ui.open_window.v1',
        response_type='code',
        state='client_authorize',
    )

    if request.user.is_authenticated():
        # Get nav counts data
        cache_key = 'nav_counts:%s' % (request.user.id)
        cc = cache.get(cache_key)

        if cc:
            data['nav_contracts'] = cc[0]
            data['nav_industryjobs'] = cc[1]
            data['nav_mail'] = cc[2]
        else:
            if character_ids is None:
                character_ids = list(
                    Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))

            # Aggregate outstanding contracts
            corp_contract_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_CONTRACTS_MASK)
            contracts = Contract.objects.filter(
                Q(character__in=character_ids, corporation__isnull=True)
                |
                Q(corporation__in=corp_contract_ids)
            )
            contracts = contracts.filter(status='Outstanding')

            data['nav_contracts'] = contracts.aggregate(t=Count('contract_id', distinct=True))['t']

            # Aggregate ready industry jobs
            corp_job_ids = Corporation.get_ids_with_access(request.user, APIKey.CORP_INDUSTRY_JOBS_MASK)
            jobs = IndustryJob.objects.filter(
                Q(character__in=character_ids, corporation__isnull=True)
                |
                Q(corporation__in=corp_job_ids)
            )
            jobs = jobs.filter(status=1, end_date__lte=utcnow)
            data['nav_industryjobs'] = jobs.aggregate(t=Count('id'))['t']

            # Aggregate unread mail messages
            data['nav_mail'] = MailMessage.objects.filter(
                character__in=character_ids,
                read=False,
            ).values(
                'message_id',
            ).distinct().count()

            cursor = get_cursor()
            cursor.execute(queries.buyback_contracts + ' UNION ' + queries.fuelblock_purchase_contracts)
            buyback_ids = [c[0] for c in cursor.fetchall()]
            cursor.close()

            data['nav_item_contracts'] = Contract.objects.filter(
                contract_id__in=buyback_ids,
                status='Outstanding'
            ).aggregate(t=Count('contract_id'))['t']

            cursor = get_cursor()
            cursor.execute(queries.courier_contracts)
            courier_ids = [c[0] for c in cursor.fetchall()]
            cursor.close()
            data['nav_courier_contracts'] = Contract.objects.filter(
                contract_id__in=courier_ids,
                status__in=['Outstanding','InProgress']
            ).aggregate(t=Count('contract_id'))['t']


            # Cache data
            cache_data = (data['nav_contracts'], data['nav_industryjobs'], data['nav_mail'])
            cache.set(cache_key, cache_data, 300)

        # Get queue length data
        data['task_count'] = cache.get('task_count')
        if data['task_count'] is None:
            data['task_count'] = TaskState.objects.filter(state=TaskState.QUEUED_STATE).aggregate(Count('id'))[
                'id__count']
            cache.set('task_count', data['task_count'], 60)

    return render_to_response(template, data, RequestContext(request))


def flush_cache(user):
    if user.is_authenticated():
        cache_key = 'nav_counts:%s' % (user.id)
        cache.delete(cache_key)


class TimerThing:
    def __init__(self, name):
        self.times = []
        self.add_time(name)

    def add_time(self, name):
        self.times.append([time.time(), name])

    def finished(self):
        print 'TimerThing: %s' % (self.times[0][1])
        print '-' * 23
        for i in range(1, len(self.times)):
            t, name = self.times[i]
            print '%-15s: %.3fs' % (name, t - self.times[i - 1][0])
        print '-' * 23
        print '%-15s: %.3fs' % ('total', self.times[-1][0] - self.times[0][0])


def dictfetchall(cursor):
    """Returns all rows from a cursor as a dict"""
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def total_seconds(delta):
    """Convert a datetime.timedelta object into a number of seconds"""
    return (delta.days * 24 * 60 * 60) + delta.seconds


def build_filter(filters, filter_type, filter_comp, filter_value):
    params = []

    for ft, stuff in filters.items():
        if ft == filter_type:
            continue

        for fc, fv in stuff:
            params.append(('ft', ft))
            params.append(('fc', fc))
            params.append(('fv', fv))

    params.append(('ft', filter_type))
    params.append(('fc', filter_comp))
    if type(filter_value) == unicode:
        filter_value = filter_value.encode('utf-8')
    params.append(('fv', filter_value))

    return urlencode(params)


def parse_filters(request, expected):
    """Parse filter GET variables"""
    # retrieve any supplied filter values
    f_types = request.GET.getlist('ft')
    f_comps = request.GET.getlist('fc')
    f_values = request.GET.getlist('fv')

    # run.
    filters = {}

    min_len = min(len(f_types), len(f_comps), len(f_values))
    for ft, fc, fv in zip(f_types[:min_len], f_comps[:min_len], f_values[:min_len]):
        ex = expected.get(ft)
        if ex is None:
            continue

        # If the entry must be a number, verify that
        if ex.get('number', False):
            try:
                fv = int(fv)
            except ValueError:
                continue

        # Make sure the comparison is valid
        if fc not in ex.get('comps', []):
            continue

        # Keep it
        filters.setdefault(ft, []).append([fc, fv])

    return filters


def q_reduce_or(a, b):
    return a | b


def q_reduce_and(a, b):
    return a & b


def get_cursor(db='default'):
    """
    Get a database connection cursor for db.
    """
    return connections[db].cursor()
