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
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render

from thing.utils import dictfetchall
from thing import queries
from thing.helpers import commas


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

    def __init__(self, structure, extraction, config, observer_log, ore_values, ship_m3_per_hour):
        self.name = structure.station.name
        self.is_jackpot = False

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

        self.ores = list()

        self.parse_log()

        for ore in self.ores:
            tooltip = ''
            for ship in ship_m3_per_hour:
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
                self.ore_values[ore.ore.id] = ore.ore.get_history_avg(reprocess=True, reprocess_pct=.84, pct=.8)

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
            else:
                ore.remaining_pct = 0

            self.remaining_volume = max(0, self.remaining_volume - ore.mined_volume)
            self.remaining_value = max(0.0, self.remaining_value-float(ore.mined_volume / ore.ore.volume) * ore.value_ea)

            if ore.remaining_pct == 0:
                ore.remaining_isk_per_m3 = 0
            elif ore.remaining_volume > 0:
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
    max_date = datetime.datetime.utcnow() + datetime.timedelta(days=7)

    moon_extractions = MoonExtractionHistory.objects.filter(chunk_arrival_time__gte=min_date, chunk_arrival_time__lte=max_date).order_by('chunk_arrival_time')

    ore_values = dict()

    if 'char' in request.session:
        charid = request.session['char']['id']
        waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()
    else:
        waypoint_scope = None

    ship_m3_per_hour = [
        dict(name='Venture', m3=9*60*60),
        dict(name='Procurer', m3=32*60*60),
    ]

    moon_list = []
    for e in moon_extractions:
        structure = e.structure
        cfg = MoonConfig.objects.filter(structure_id=e.structure.id).first()

        # TODO: Enable Nationalized moons based off roles?
        if cfg is None or cfg.is_nationalized:
            continue

        observer = MoonObserver.objects.filter(observer_id=structure.station_id).first()

        observer_log = None
        if observer is not None:
            observer_log = MoonObserverEntry.objects.filter(
                observer_id=observer.id,
                last_updated__gte=e.chunk_arrival_time,
                last_updated__lte=e.chunk_arrival_time + datetime.timedelta(days=2))

        details = MoonDetails(structure, e, cfg, observer_log, ore_values, ship_m3_per_hour)

        moon_list.append(details)

    out = render_page(
        'pgsus/extractions.html',
        dict(
            moon_list=moon_list,
            show_waypoint=waypoint_scope is not None,
        ),
        request,
    )

    return out

def refinerylist(request):
    if 'char' not in request.session:
        return redirect('/?login=1')

    charid = request.session['char']['id']

    role = CharacterRole.objects.filter(character_id=charid, role='moon').first()

    if role is None:
        return redirect('/?perm=1')

    corpid = role.character.corporation.id

    if request.method == 'POST':
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

    struct_services = StructureService.objects.filter(name='Moon Drilling', structure__station__corporation_id=corpid)

    struct_list = dict()

    moon_system_ids = set([s.structure.station.system_id for s in struct_services.filter(state='online')])

    repro_services = StructureService.objects.filter(name='Reprocessing', structure__station__name__iregex='DRILL', structure__station__corporation_id=corpid)

    repro_system_ids = set([s.structure.station.system_id for s in repro_services])

    system_ids_missing_repros = moon_system_ids - repro_system_ids

    systems_missing_repros = System.objects.filter(id__in=system_ids_missing_repros)

    region_list = set()
    constellation_list = set()
    system_list = set()

    type_list = ['N64', 'R64', 'D64', 'R32', 'R16', 'R4', 'ABC']

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

        if type_filter is not None:
            if type_filter == 'D64':
                try:
                    if structure.station.system.alliance.name == 'Pandemic Horde':
                        if type_filter not in structure.station.name:
                            continue
                except:
                    pass
            elif type_filter not in structure.station.name:
                continue

        filtered_structures += 1

        structure.z_not_extracting = structure.z_moon_info is None\
            or structure.z_moon_info.chunk_arrival_time < datetime.datetime.utcnow()

        config = structure.get_config()

        structure.z_config = config or MoonConfig(chunk_days=None)

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



