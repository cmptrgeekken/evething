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

from django.db import connections

from collections import defaultdict

from thing import queries

from thing.utils import dictfetchall

from thing.models import *  # NOPEP8
from thing.stuff import render_page, datetime  # NOPEP8
import time
from thing.helpers import humanize

from pgsus import Calculator

from math import ceil

import re

from pgsus.parser import parse, iter_types
import evepaste

from pprint import pprint, pformat

from django.shortcuts import redirect, render


def refinerylist(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role='moon').first()

    if role is None:
        return redirect('/?perm=1')

    corpid = role.character.corporation.id

    waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()

    struct_services = StructureService.objects.filter(name='Moon Drilling', structure__station__corporation_id=corpid)

    struct_list = dict()

    for service in struct_services:
        structure = service.structure
        structure.z_online = service.state == 'online'
        structure.z_moon_info = MoonExtraction.objects.filter(structure_id=structure.station_id).first()

        structure.z_not_extracting = structure.z_moon_info is None\
            or structure.z_moon_info.chunk_arrival_time < datetime.datetime.utcnow()

        cycle_time = 28
        try:
            if structure.station.system.alliance_id is None\
                    or structure.station.system.alliance.name != 'Pandemic Horde':
                cycle_time = 7
        except:
            cycle_time = 7

        structure.z_cycle_time = cycle_time

        if structure.z_moon_info is None:
            structure.z_next_chunk_time = datetime.datetime.utcnow().replace(second=0, microsecond=0) + datetime.timedelta(days=cycle_time)
        else:
            structure.z_next_chunk_time = structure.z_moon_info.chunk_arrival_time + datetime.timedelta(days=cycle_time)

        if service.structure.id not in struct_list:
            struct_list[service.structure.id] = service.structure

    def service_sort(itema, itemb):
        if not itema.z_online:
            return 1
        if not itemb.z_online:
            return -1

        if itema.z_not_extracting:
            return -1
        if itemb.z_not_extracting:
            return 1

        return -1 if itema.z_moon_info.chunk_arrival_time < itemb.z_moon_info.chunk_arrival_time else 1

    struct_list = struct_list.values()

    struct_list.sort(service_sort)

    out = render_page(
        'pgsus/refinerylist.html',
        dict(
            structures=struct_list,
            add_waypoint=waypoint_scope is not None,
        ),
        request,
    )

    return out



