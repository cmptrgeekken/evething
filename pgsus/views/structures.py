#!/usr/bin/python
# encoding=utf8
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

from thing.models import *  # NOPEP8
from thing.stuff import render_page, datetime  # NOPEP8
from thing.utils import ApiHelper
from thing import queries
import re
import json

from django.db import connections

from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache

from thing.utils import dictfetchall

from thing.helpers import humanize, commas

from ics import Calendar, Event

import uuid
import random


def mooncomp(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role='moon').first()

    if role is None:
        return redirect('/?perm=1')

    error_lines = []
    moon_comps = ''

    if request.method == 'POST':
        moon_comps = request.POST.get('moon_comps')

        comp_lines = moon_comps.splitlines()

        for i in range(0, len(comp_lines)):
            line = comp_lines[i]
            comp_cols = line.split('\t')

            ore_errors = []

            if len(comp_cols) != 10:
                error_lines.append('Line %d: Not enough columns' % (i+1))
                continue

            structure_id, first_ore_name, first_ore_pct, second_ore_name, second_ore_pct, third_ore_name, third_ore_pct,\
                fourth_ore_name, fourth_ore_pct, is_national = comp_cols

            first_ore = Item.objects.filter(name=first_ore_name).first()
            second_ore = Item.objects.filter(name=second_ore_name).first()

            if not first_ore:
                ore_errors.append(first_ore_name)

            if not second_ore:
                ore_errors.append(second_ore_name)

            if third_ore_name:
                third_ore = Item.objects.filter(name=third_ore_name).first()
                if not third_ore:
                    ore_errors.append(third_ore_name)
            else:
                third_ore = None

            if fourth_ore_name:
                fourth_ore = Item.objects.filter(name=fourth_ore_name).first()
                if not fourth_ore:
                    ore_errors.append(fourth_ore_name)
            else:
                fourth_ore = None

            if ore_errors:
                error_lines.append('Line %d: Ore names not recognized: %s' % (i+1, ', '.join(ore_errors)))
                continue

            structure = Structure.objects.filter(station_id=structure_id).first()
            if structure is None:
                error_lines.append('Line %d: Structure not found: %s' % (i + 1, structure_id))
                continue

            moon_config = MoonConfig.objects.filter(structure_id=structure.id).first()

            if moon_config is None:
                moon_config = MoonConfig(
                    structure_id=structure.id,
                )

            moon_config.first_ore_id = first_ore.id
            moon_config.first_ore_pct = float(first_ore_pct.strip('%'))/100
            moon_config.second_ore_id = second_ore.id
            moon_config.second_ore_pct = float(second_ore_pct.strip('%'))/100
            moon_config.third_ore_id = third_ore.id if third_ore is not None else None
            moon_config.third_ore_pct = float(third_ore_pct.strip('%'))/100 if third_ore else None
            moon_config.fourth_ore_id = fourth_ore.id if fourth_ore else None
            moon_config.fourth_ore_pct = float(fourth_ore_pct.strip('%'))/100 if fourth_ore else None
            moon_config.is_nationalized = is_national == 'Y'

            moon_config.save()

    request.session['comp_errors'] = error_lines
    request.session['moon_comps'] = moon_comps

    return redirect(reverse(refinerylist))


class MoonOreEntry:
    def __init__(self, ore, pct, total_volume):
        self.ore = ore
        self.pct = pct
        self.total_volume = total_volume
        self.refinery = None

        self.name = self.ore.name

        self.total_value = 0

        self.value_ea = 0

        self.remaining_volume = 0
        self.remaining_value = 0

        self.mined_volume = 0
        self.mined_value = 0

        self.remaining_isk_per_m3 = 0
        self.remaining_pct = 0

        self.is_jackpot = False

        self.type = None

class MoonDetails:

    def __init__(self, structure, extraction, config, observer_log, ore_values, ship_m3_per_hour, refinery):
        self.name = structure.station.name
        self.is_jackpot = False
        self.refinery = refinery

        if datetime.datetime.utcnow() > extraction.natural_decay_time \
                or extraction.laser_fire_time is not None:
            self.is_popped = True
        else:
            self.is_popped = False

        self.is_poppable = extraction.chunk_arrival_time <= datetime.datetime.utcnow()

        self.structure = structure
        self.extraction = extraction
        self.config = config
        self.log = observer_log
        self.ore_values = ore_values
        self.remaining_pct = 0

        self.ore_types = list()

        self.chunk_days = extraction.chunk_minutes / 60 / 24

        self.expiration_time = extraction.natural_decay_time + datetime.timedelta(days=2)

        self.total_volume = self.remaining_volume = extraction.chunk_minutes * 333
        self.total_value = 0

        self.remaining_value = 0

        self.remaining_isk_per_m3 = 0

        self.last_mined = None

        self.ores = list()

        self.parse_log()

        for ore in self.ores:
            tooltip = ''
            for ship in ship_m3_per_hour:
                if 'ignore' in ship and ship['ignore'] in self.name:
                    continue
                if tooltip:
                    tooltip += ' / '

                tooltip += '%s: %s ISK' % (ship['name'], commas(float(ship['m3'])*ore.remaining_isk_per_m3, 0))

            tooltip = 'Hourly - ' + tooltip

            ore.ship_m3_tooltip = tooltip

        tooltip = ''
        for ship in ship_m3_per_hour:
            if tooltip:
                tooltip += ' / '

            tooltip += '%s: %s ISK' % (ship['name'], commas(float(ship['m3']) * self.remaining_isk_per_m3, 0))

        self.ship_m3_tooltip = 'Hourly - ' + tooltip

    def to_event(self, base_url):
        rd = random.Random()
        rd.seed(self.extraction.id)

        desc = "Chunk Time: %s days" % self.chunk_days

        if self.total_value is not None:
            desc += "\nTotal Value: %s ISK\n" % humanize(self.total_value)
        else:
            desc += "Total Value: Unknown"

        for ore in self.ores:
            desc += "\n(%s) %s%% %s\n %s ISK/m<sup>3</sup>" % (ore.type, commas(ore.pct*100, 0), ore.ore.name, commas(ore.remaining_isk_per_m3, 0))
            desc += "\n Ore Value: %s ISK" % commas(float(ore.total_volume) * ore.remaining_isk_per_m3, 0)

        e = Event(
            name=self.name,
            begin=self.extraction.chunk_arrival_time,
            duration=datetime.timedelta(hours=3),
            url=base_url + str(self.extraction.id),
            uid=str(uuid.UUID(int=rd.getrandbits(128))),
            description=desc
        )
        return e

    def parse_log(self):
        try:
            first_ore = self.config.first_ore
        except:
            return

        self.ores.append(
            MoonOreEntry(
                ore=self.config.first_ore,
                pct=self.config.first_ore_pct,
                total_volume=self.config.first_ore_pct*self.total_volume,
            )
        )

        self.ores.append(
            MoonOreEntry(
                ore=self.config.second_ore,
                pct=self.config.second_ore_pct,
                total_volume=self.config.second_ore_pct*self.total_volume,
            )
        )

        if self.config.third_ore_id is not None:
            self.ores.append(
                MoonOreEntry(
                    ore=self.config.third_ore,
                    pct=self.config.third_ore_pct,
                    total_volume=self.config.third_ore_pct*self.total_volume,
                )
            )

        if self.config.fourth_ore_id is not None:
            self.ores.append(
                MoonOreEntry(
                    ore=self.config.fourth_ore,
                    pct=self.config.fourth_ore_pct,
                    total_volume=self.config.fourth_ore_pct * self.total_volume,
                )
            )

        ore_types = set()

        for ore in self.ores:

            ore.remaining_volume = ore.total_volume = ore.pct * self.total_volume
            if ore.ore.id not in self.ore_values:
                self.ore_values[ore.ore.id] = .9*ore.ore.get_price(buy=True,reprocess=True, reprocess_pct=.843)

            ore.value_ea = self.ore_values[ore.ore.id]

            ore.total_value = ore.remaining_value = float(ore.total_volume / ore.ore.volume) * ore.value_ea

            if self.log is not None:
                for l in self.log:
                    if ore.name not in l.type.name:
                        continue

                    if 'Twinkling' in l.type.name or 'Shining' in l.type.name\
                            or 'Glowing' in l.type.name or 'Shimmering' in l.type.name:
                        self.is_jackpot = True
                        ore.is_jackpot = True

                    ore.mined_volume += l.quantity * l.type.volume

                    self.is_popped = True

                    if self.last_mined is None or l.end_time > self.last_mined:
                        self.last_mined = l.end_time

            if ore.is_jackpot:
                ore.total_value *= 2
                ore.value_ea *= 2

            self.total_value += ore.total_value
            self.remaining_value += ore.total_value

            ore.remaining_volume = max(0, ore.remaining_volume - ore.mined_volume)
            ore.remaining_value = float(ore.remaining_volume / ore.ore.volume) * ore.value_ea

            ore.remaining_pct = float(ore.remaining_volume / ore.total_volume)

            if ore.remaining_pct > .6:
                ore.remaining_pct = .6
            elif ore.remaining_pct > .3:
                ore.remaining_pct = .3

            self.remaining_volume = max(0, self.remaining_volume - ore.mined_volume)
            self.remaining_value = max(0.0, self.remaining_value-float(ore.mined_volume / ore.ore.volume) * ore.value_ea)

            if ore.remaining_volume > 0:
                ore.remaining_isk_per_m3 = ore.remaining_value / float(ore.remaining_volume)

            ore_type = ore.ore.item_group.name

            if 'Exceptional' in ore_type:
                ore_types.add('1R64')
                ore.type = 'R64'
            elif 'Rare' in ore_type:
                ore_types.add('2R32')
                ore.type = 'R32'
            elif 'Uncommon' in ore_type:
                ore_types.add('3R16')
                ore.type = 'R16'
            elif 'Common' in ore_type:
                ore_types.add('4R8')
                ore.type = 'R8'
            elif 'Ubiquitous' in ore_type:
                ore_types.add('5R4')
                ore.type = 'R4'
            else:
                ore_types.add('6ORE')
                ore.type = 'ORE'

        if self.remaining_volume > 0:
            self.remaining_isk_per_m3 = self.remaining_value / float(self.remaining_volume)

        self.remaining_pct = float(self.remaining_value / self.total_value)

        if self.remaining_pct > 0.9:
            self.remaining_pct = 1
        elif self.remaining_pct > 0.6:
            self.remaining_pct = 0.6
        elif self.remaining_pct > 0.3:
            self.remaining_pct = 0.3
        else:
            self.remaining_pct = 0

        self.ore_types = list(ore_types)

        self.ore_types.sort()
        for i in range(0, len(self.ore_types)):
            self.ore_types[i] = self.ore_types[i][1:]

        def sort_ores(a, b):
            return -1 if a.remaining_isk_per_m3 > b.remaining_isk_per_m3 else 1

        self.ores.sort(sort_ores)


def extractions(request):
    min_date = datetime.datetime.utcnow() + datetime.timedelta(days=-2)
    min_date_rigged = datetime.datetime.utcnow() + datetime.timedelta(days=-4)
    max_visible_days = 7

    ore_values = dict()

    if 'char' in request.session:
        charid = request.session['char']['id']
        waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()
        role = CharacterRole.objects.filter(character_id=charid, role__in=['moon','spodcmd', 'moonbean']).values_list('role', flat=True).first()
    else:
        waypoint_scope = None
        role = None
    
    ship_m3_per_hour = [
        dict(name='Venture', m3=9*60*60),
        dict(name='Procurer', m3=32*60*60),
        dict(name='Rorqual', m3=175*60*60, ignore='R64')
    ]

    ticker = request.GET.get('ticker') or 'REKTD'

    moon_type = (request.GET.get('type') or 'public').lower()
    if role is None:
        moon_type = 'public'
    elif moon_type.lower() == 'r16':
        moon_type = 's16'

    if moon_type == 'n64':
        min_date = min_date_rigged

    if role is not None:
        max_visible_days = 25
    
    max_date = datetime.datetime.utcnow() + datetime.timedelta(days=max_visible_days)
    cache_key = 'extractions-%s-%s-%d' % (ticker, moon_type, max_visible_days)

    moon_list = cache.get(cache_key)

    filter_types = ['Public']

    if role == 'moon' or role == 'spodcmd':
        filter_types.append('N64')
        filter_types.append('S16')


    if moon_list is None:
        moon_list = dict()
        
        moon_extractions = MoonExtractionHistory.objects.filter(chunk_arrival_time__gte=min_date, chunk_arrival_time__lte=max_date).order_by('chunk_arrival_time')

        refineries = dict()
        
        for e in moon_extractions:
            structure = e.structure
            if structure.station.corporation_id is None\
                or structure.station.corporation.alliance.short_name != ticker:
                continue

            system = structure.station.system.name

            if system not in refineries:
                repro_structure = StructureService.objects.filter(name='Reprocessing', structure__station__corporation__alliance__short_name=ticker, structure__station__name__iregex='DRILL', state='online',structure__station__system__name=system).first()

                #repro_structure = Station.objects.filter(name__iregex='Refinery', corporation__alliance__short_name=ticker, system__name=system).first()

                if repro_structure is not None:
                    refineries[system] = repro_structure.structure.station.name

            if system in refineries:
                refinery = refineries[system]
            else:
                refinery = None


            cfg = MoonConfig.objects.filter(structure_id=e.structure.id).first()
            if cfg is None:
                continue

            if moon_type == 'public':
                if cfg.is_nationalized:
                    continue
            elif moon_type.lower() not in structure.station.name.lower():
                continue

            observer = MoonObserver.objects.filter(observer_id=structure.station_id).first()

            observer_log = []
            if observer is not None:
                observer_log = MoonObserverEntry.objects.filter(
                    observer_id=observer.id,
                    last_updated__gte=e.chunk_arrival_time,
                    last_updated__lte=e.chunk_arrival_time + datetime.timedelta(days=2))

            details = MoonDetails(structure, e, cfg, observer_log, ore_values, ship_m3_per_hour, refinery)

            moon_list[structure.id] = details

        moon_list = moon_list.values()

        moon_list.sort(key=lambda x: x.extraction.chunk_arrival_time)

        cache.set(cache_key, moon_list, 60*10)

    if 'format' in request.GET and request.GET.get('format') == 'ical':
        cal = Calendar(imports=[
            'BEGIN:VCALENDAR',
            'PRODID:-//PGSUS//Penny\'s Flying Circus//EN',
            'X-WR-CALNAME:%s Moon Extractions' % ticker,
            'X-PUBLISHED-TTL:PT1H',
            'END:VCALENDAR',
        ])
        for l in moon_list:
            base_url = request.build_absolute_uri(reverse(extractions))

            event_url = "%s?ticker=%s&event=" % (base_url, ticker)

            cal.events.append(l.to_event(event_url))

        response = HttpResponse(str(cal), content_type='text/calendar')

        response['Content-Disposition'] = 'attachment;filename="Moon Schedule.ics"'

        return response

    out = render_page(
        'pgsus/extractions.html',
        dict(
            moon_list=moon_list,
            show_waypoint=waypoint_scope is not None,
            filter_types=filter_types,
            moon_type=moon_type
        ),
        request,
    )

    if 'format' in request.GET and request.GET.get('format') == 'json':
        return JsonResponse(moon_list, safe=False)

    return out

def gates(request):
    if 'char' not in request.session:
        return redirect('/?login=1');

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role__in=['gatewatch']).first()

    if role is None:
        return redirect('/?perm=1')

    alliance_id = role.character.corporation.alliance_id

    results = None #cache.get('gates')
    if results is None:
        results = dictfetchall(queries.jumpbridge_lo_quantity % alliance_id)

        cache.set('structures-gates-%d' % alliance_id, results)


    lo_quantities = dictfetchall(queries.lo_station_quantities % alliance_id)

    for r in results:
        sys = r['station_name'].split(' » '.decode('utf8'))[0]
        for q in lo_quantities:
            if sys in q['station_name']:
                if 'stations' not in r:
                    r['stations'] = list()
                r['stations'].append('<b>%s</b>: %s LO' % (q['station_name'], commas(q['qty'])))
            

    return render_page(
                'pgsus/gates.html',
                dict(
                    gates=results
                ),
                request
                )

class IHub:
    def __init__(self, entry):
        self.system = entry['system']
        self.constellation = entry['constellation']
        self.region = entry['region']
        self.upgrades = list()
        self.last_updated = entry['last_updated']
        self.corp_ticker = entry['corp_ticker']

def ihubs(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role__in=['structure']).first()

    if role is None:
        return redirect('/?perm=1')

    alliance_id = role.character.corporation.alliance_id

    ihubs = cache.get('ihubs')
    if ihubs is None:
        ihubs = dictfetchall(queries.ihub_upgrades % alliance_id)
        cache.set('structures-ihubs-%d' % alliance_id, ihubs)

    region_list = set()
    constellation_list = set()
    system_list = set()

    type_list = set()

    region_filter = request.GET.get('region')
    constellation_filter = request.GET.get('constellation')
    system_filter = request.GET.get('system')
    type_filter = request.GET.get('type')

    results = dict()

    for ihub in ihubs:
        region_list.add(ihub['region'])
        constellation_list.add(ihub['constellation'])
        system_list.add(ihub['system'])

        type_name = re.sub(r"\d+$", "", ihub['upgrade'])

        type_list.add(type_name)

	if region_filter and region_filter != ihub['region']:
            continue
        if constellation_filter and constellation_filter != ihub['constellation']:
            continue
        if system_filter and system_filter != ihub['system']:
            continue
        if type_filter and type_filter not in ihub['upgrade']:
            continue

        if ihub['system'] not in results:
            results[ihub['system']] = IHub(ihub)

        if ihub['state'] == 'Offline':
            ihub['state_color'] = 'firebrick'
        else:
            ihub['state_color'] = 'forestgreen'

        results[ihub['system']].upgrades.append("%s <span style='color: %s'>(%s)</span>" % (ihub['upgrade'], ihub['state_color'], ihub['state']))

    def ihub_sort(itema, itemb):
        if itema.region < itemb.region:
            return -1
        if itema.region > itemb.region:
            return 1
        if itema.system < itemb.system:
            return -1
        return 1

    results_list = results.values()

    results_list.sort(ihub_sort)


    region_list = list(region_list)
    constellation_list = list(constellation_list)
    system_list = list(system_list)
    type_list = list(type_list)

    region_list.sort()
    constellation_list.sort()
    system_list.sort()
    type_list.sort()

    return render_page(
        'pgsus/ihublist.html',
        dict(
            results=results_list,
            regions=region_list,
            constellations=constellation_list,
            systems=system_list,
            types=type_list,
            region=region_filter,
            constellation=constellation_filter,
            system=system_filter,
            type=type_filter,
        ),
        request,
    )
     




def refinerylist(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role__in=['moon','moonbean']).first()

    if role is None:
        return redirect('/?perm=1')

    is_admin = role.role == 'moon'

    if role.character.corporation_id is None:
        return render_page('pgsus/error.html', dict(message = 'No corporation associated with your character. Please contact KenGeorge Beck for assistance.'), request)

    allianceid = role.character.corporation.alliance_id

    if is_admin and request.method == 'POST':
        structure_id = request.POST.get('structure_id')
        extraction_id = request.POST.get('extraction_id')
        next_date_override = request.POST.get('next_date_override') or None
        chunk_time = request.POST.get('chunk_time') or None
        is_nationalized = request.POST.get('is_nationalized') == '1'
        ignore_refire = request.POST.get('ignore_refire') == '1'
        ignore_scheduling = request.POST.get('ignore_scheduling') == '1'
        manually_fired = request.POST.get('manually_fired') == '1'

        config = MoonConfig.objects.filter(structure_id=structure_id).first()
        if config is None:
            config = MoonConfig(
                structure_id=structure_id
            )

        if extraction_id is not None:
            extraction = MoonExtraction.objects.filter(id=extraction_id).first()
            if extraction is not None:
                extraction.manually_fired = manually_fired
                extraction.save()

        config.is_nationalized = is_nationalized
        config.next_date_override=next_date_override
        config.chunk_days = chunk_time
        config.ignore_refire = ignore_refire
        config.ignore_scheduling = ignore_scheduling

        config.save()

    waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()

    struct_services = StructureService.objects.filter(name='Moon Drilling', structure__station__corporation__alliance_id=allianceid)

    struct_list = dict()

    moon_system_ids = set([s.structure.station.system_id for s in struct_services.filter(state='online')])

    repro_services = StructureService.objects.filter(name='Reprocessing', structure__station__name__iregex='DRILL', structure__station__corporation__alliance_id=allianceid)

    repro_system_ids = set([s.structure.station.system_id for s in repro_services])

    system_ids_missing_repros = moon_system_ids - repro_system_ids

    systems_missing_repros = System.objects.filter(id__in=system_ids_missing_repros)

    region_list = set()
    constellation_list = set()
    system_list = set()

    type_list = ['N64', 'R64', 'R32', 'S16']

    region_filter = request.GET.get('region')
    constellation_filter = request.GET.get('constellation')
    system_filter = request.GET.get('system')
    type_filter = request.GET.get('type')
    search_filter = request.GET.get('search')

    total_structures = 0
    filtered_structures = 0

    for service in struct_services:
        structure = service.structure
        structure.z_online = service.state == 'online'
        structure.z_moon_info = MoonExtractionHistory.objects.filter(structure_id=structure.station_id).order_by('-chunk_arrival_time').first()
        structure.z_last_extraction = MoonExtractionHistory.objects.filter(structure_id=structure.station_id).exclude(laser_fired_by_id__isnull=True).order_by('-chunk_arrival_time').first()
        structure.z_current_extraction = MoonExtractionHistory.objects.filter(structure_id=structure.station_id).exclude(extraction_started_by_id__isnull=True).order_by('-chunk_arrival_time').first()

        structure.z_last_exploder = None
        structure.z_last_firer = None

        if 'Horde' in structure.station.corporation.name\
                and (structure.station.system.constellation.region.name == 'Pure Blind' or structure.station.system.constellation.region.name == 'Fade'\
                or structure.station.system.constellation.region.name == 'Cloud Ring'):
            continue


        if structure.z_last_extraction is not None:
            if structure.z_last_extraction.laser_fired_by_id:
                structure.z_last_exploder = structure.z_last_extraction.laser_fired_by.name

        if structure.z_current_extraction is not None:
            if structure.z_current_extraction.extraction_started_by_id:
                structure.z_last_firer = structure.z_current_extraction.extraction_started_by.name

        region_list.add(structure.station.system.constellation.region.name)
        constellation_list.add(structure.station.system.constellation.name)
        system_list.add(structure.station.system.name)

        total_structures += 1

        if region_filter and structure.station.system.constellation.region.name != region_filter:
            continue

        if constellation_filter and structure.station.system.constellation.name != constellation_filter:
            continue

        if system_filter and structure.station.system.name != system_filter:
            continue

        if search_filter and search_filter not in structure.station.name:
            continue
        
        config = structure.get_config()

        if type_filter is not None:
            if type_filter == 'D64':
                try:
                    if structure.station.system.alliance.name == 'Pandemic Horde':
                        if type_filter not in structure.station.name:
                            continue
                except:
                    pass
            elif type_filter == 'N64':
                if type_filter not in structure.station.name: #config is None or not config.is_nationalized:
                    continue
            elif type_filter not in structure.station.name:
                continue

        filtered_structures += 1

        structure.z_not_extracting = structure.z_moon_info is None\
            or structure.z_moon_info.chunk_arrival_time < datetime.datetime.utcnow()

        structure.z_config = config or MoonConfig(chunk_days=None)

        if not is_admin:
            if structure.z_config.is_nationalized or not structure.z_not_extracting or structure.z_config.ignore_refire or not structure.z_online:
                continue

        structure.z_next_chunk_time = None

        if config is None or config.chunk_days is None:
            cycle_time = 28
            try:
                if structure.station.system.alliance_id is None\
                        or structure.station.system.alliance.name != 'Pandemic Horde':
                    cycle_time = 7
            except:
                cycle_time = 7
        else:
            cycle_time = config.chunk_days

        if config is None or config.next_date_override is None:
            if structure.z_moon_info is None:
                structure.z_next_chunk_time = datetime.datetime.utcnow().replace(second=0, microsecond=0) + datetime.timedelta(days=cycle_time)
            else:
                structure.z_next_chunk_time = structure.z_moon_info.chunk_arrival_time + datetime.timedelta(days=cycle_time)
        else:
            next_date_override = config.next_date_override
            while next_date_override <= datetime.datetime.utcnow():
                next_date_override += datetime.timedelta(days=cycle_time)
            structure.z_next_chunk_time = next_date_override

        structure.z_cycle_time = cycle_time

        # If we're under 6 days for this chunk, set chunk to the next cycle time
        if structure.z_next_chunk_time < datetime.datetime.utcnow() + datetime.timedelta(days=6):
            if cycle_time > 50 and structure.z_moon_info.chunk_arrival_time < structure.z_next_chunk_time:
                structure.z_chunk_start_time = structure.z_next_chunk_time

            structure.z_next_chunk_time += datetime.timedelta(days=cycle_time)

        else:
            structure.z_chunk_start_time = None

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

    error_lines = []
    moon_comps = ''

    if 'comp_errors' in request.session and request.session['comp_errors']:
        error_lines = request.session['comp_errors']
        moon_comps = request.session['moon_comps']
        request.session['comp_errors'] = None
        request.session['moon_comps'] = None

    region_list = list(region_list)
    constellation_list = list(constellation_list)
    system_list = list(system_list)

    region_list.sort()
    constellation_list.sort()
    system_list.sort()

    out = render_page(
        'pgsus/refinerylist.html',
        dict(
            structures=struct_list,
            add_waypoint=waypoint_scope is not None,
            systems_missing_repros=systems_missing_repros,
            error_lines=error_lines,
            is_admin=is_admin,
            moon_comps=moon_comps,
            regions=region_list,
            constellations=constellation_list,
            systems=system_list,
            types=type_list,
            region=region_filter,
            constellation=constellation_filter,
            system=system_filter,
            type=type_filter,
            search=search_filter,
            ttl_structure_count=total_structures,
            filtered_structure_count=filtered_structures,
        ),
        request,
    )

    return out

def add_gate(request):
    scope = None
    if 'char' in request.session:
        charid = request.session['char']['id']

        scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-universe.read_structures.v1').first()

    if scope is None:
        return redirect('/?perm=1')

    system = request.GET.get('system')
      
    structs = list()

    message = ''
    helper = ApiHelper()

    if system is not None:

        success, data = helper.fetch_esi_url('https://esi.evetech.net/latest/characters/%s/search/?categories=structure&search=%s&datasource=tranquility' % (charid, system), scope.character)

        if not success:
            message = 'Failed 1: %s' % data

        if success:
            structures = json.loads(data)

            for s in structures['structure']:
                success, s_data = helper.fetch_esi_url('https://esi.evetech.net/latest/universe/structures/%s/?datasource=tranquility' % s, scope.character)

                if not success:
                    message += 'Failed 2: %s' % s_data
                    break

                if success:
                    structure = json.loads(s_data)

                    message += 'Found Structure: %s ' % structure['name']

                    if structure['type_id'] == 35841:
                        db_struct = Station.objects.filter(id=s).first()

                        if db_struct is None:
                            db_struct = Station()
                            db_struct.id = s

                        db_struct.name = structure['name']
                        db_struct.short_name = structure['name']
                        db_struct.type_id = structure['type_id']
                        db_struct.system_id = structure['solar_system_id']
                        db_struct.is_citadel = True
                        db_struct.is_unknown = False
                        db_struct.corporation_id = structure['owner_id']

                        db_struct.save()

                        structs.append(db_struct)
    elif request.GET.get('bm') == '1':
        # Load from bookmarks
        scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-bookmarks.read_corporation_bookmarks.v1').first()
        if scope is None:
            return redirect('/?perms=1')

        success, data = helper.fetch_esi_url('https://esi.evetech.net/latest/corporations/%s/bookmarks/?datasource=tranquility' % scope.character.corporation_id, scope.character)

        if success:
            bms = json.loads(data)

            message += 'Success!'

            for bm in bms:
                if 'item' not in bm or bm['item']['type_id'] != 35841:
                    continue

                system = System.objects.filter(id=bm['location_id']).first()
    
                struct = Station.objects.filter(type_id=35841, system_id=system.id).first()
                if struct is None:
                    struct = Station()
                struct_strip = r'\s*\( Upwell Jump Gate \).*'
                struct_name = re.sub(struct_strip, '', bm['label'])
                struct.id = bm['bookmark_id']

                struct.name = struct_name
                struct.type_id = 35841
                struct.system_id = system.id
                struct.is_citadel = True
                struct.is_unknown = False
                struct.corporation_id = 1 #Unknown

                struct.save()

                structs.append(struct)
        else:
            message += data


    return render_page('pgsus/addgate.html', dict(
        added_structs=structs,
        message=message
        ), request)
    




def route(request):
    from pgsus.esi_routes import dijkstra, Graph

    starmap = None #cache.get('route-starmap')
    start_system = request.GET.get('start')
    end_system = request.GET.get('end')
    ignore_external = request.GET.get('ignore_external') == '1'
    ignored_jgs = request.GET.getlist('ignored')

    if starmap is None:
        starmap = dict()
        map_data = dictfetchall('select jg.*,1 AS needs_waypoint, IF((SELECT MAX(last_updated) FROM thing_jumpgate_history jgh WHERE jgh.station_id=jg.id) > DATE_ADD(NOW(), INTERVAL -1 DAY),1,0) AS in_alliance from thing_jumpgates jg inner join thing_station st on jg.id=st.id inner join thing_corporation c on st.corporation_id=c.id UNION SELECT *, 0 AS needs_waypoint, 1 AS in_alliance FROM thing_stargate')

        for d in map_data:
            system_id = int(d['system_id'])
            entry = starmap.get(system_id)
            if entry is None:
                entry = dict(e_neighbors=list(), neighbors=list(), security=0.0, waypoints=dict())

            entry['neighbors'].append(int(d['destination_system_id']))
            if d['in_alliance'] == 0:
                entry['e_neighbors'].append(int(d['destination_system_id']))
            if d['needs_waypoint'] == 1:
                entry['waypoints'][d['destination_system_id']] = int(d['id'])

            starmap[system_id] = entry

    cache.set('route-starmap', starmap, 60*30)

    current_jbs = dictfetchall(queries.current_bridges)

    jb_network = list()
    jb_lookup = set()

    for jb in current_jbs:
        if jb['start'] not in jb_lookup and jb['end'] not in jb_lookup:
            jb_network.append(jb)

        jb_lookup.add(jb['start'])
        jb_lookup.add(jb['end'])

    graph = Graph(starmap)

    optimal_route = list()

    if 'char' in request.session:
        charid = request.session['char']['id']
        waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()
    else:
        waypoint_scope = None

    maps_route = ''
    maps_link = None

    if start_system is not None and end_system is not None:
        start = System.objects.filter(name=start_system).first()
        end = System.objects.filter(name=end_system).first()

        end_systems = list()

        if end.name == '2Q-I6Q':
            for s in ['O-VWPB', 'NQ-9IH', 'RQOO-U', 'SH1-6P']:
                sys = System.objects.filter(name=s).first()

                if sys is not None:
                    end_systems.append(sys.id)
        else:
            end_systems.append(end.id)


        route_ids = dijkstra(graph, start.id, end_systems, ignore_external, ignored_jgs)

        systems = dict((s.id, s) for s in System.objects.filter(id__in=route_ids))

        maps_route = start.name

        for i in range(0,len(route_ids)):
            system = systems[route_ids[i]]
            next_system = None
            waypoint_is_jb = False

            if i < len(route_ids)-1:
                next_system = systems[route_ids[i+1]]

                waypoint = graph.waypoint(system.id, next_system.id)
                waypoint_is_jb = True
            elif graph.waypoint(route_ids[i-1], system.id) is None:
                waypoint = system.id
            else:
                waypoint = None

            if waypoint is not None:
                if next_system is not None:
                    maps_route += ':%s::%s' % (system.name,next_system.name)
                else:
                    maps_route += ':%s' % system.name

            system.waypoint = waypoint
            system.waypoint_is_jb = waypoint_is_jb

            optimal_route.append(system)


    return render_page('pgsus/route.html', dict(
        route=optimal_route, 
        start=start_system,
        end=end_system, 
        show_waypoints=waypoint_scope is not None, 
        maps_link='http://evemaps.dotlan.net/route/%s' % maps_route,
        svg_link='/svg?type=universe&path=%s' % maps_route,
        page_path=request.get_full_path(),
        current_jbs=jb_network,
        ignore_external=ignore_external

        ), request)


def get_cursor(db='default'):
        return connections[db].cursor()
