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

def extractions(request):
    min_date = datetime.datetime.utcnow() + datetime.timedelta(days=-2)
    max_date = datetime.datetime.utcnow() + datetime.timedelta(days=2)

    moon_configs = MoonConfig.objects.filter(last_chunk_time__gte=min_date, last_chunk_time__lte=max_date).order_by('last_chunk_time')

    structures = []
    for cfg in moon_configs:
        structure = cfg.structure

        structure.z_extraction = MoonExtraction.objects.filter(structure_id=structure.id).first()

        extraction_ttl_m3 = 333 * cfg.last_chunk_minutes
        extraction_remaining_m3 = extraction_ttl_m3
        extraction_ttl_value = float()
        extraction_remaining_value = float()

        ores = [
            dict(
                ore=cfg.first_ore,
                total_m3=cfg.first_ore_pct*extraction_ttl_m3,
            ),
            dict(
                ore=cfg.second_ore,
                total_m3=cfg.second_ore_pct*extraction_ttl_m3
            )
        ]

        if cfg.third_ore_id is not None:
            ores.append(dict(
                ore=cfg.third_ore,
                total_m3=cfg.third_ore_pct*extraction_ttl_m3,
            ))

        if cfg.fourth_ore_id is not None:
            ores.append(dict(
                ore=cfg.fourth_ore,
                total_m3=cfg.fourth_ore_pct*extraction_ttl_m3,
            ))

        ore_types = set()

        for ore in ores:
            ore_type = ore['ore'].item_group.name

            if 'Exceptional' in ore_type:
                ore_types.add('R64')
            elif 'Rare' in ore_type:
                ore_types.add('R32')
            elif 'Uncommon' in ore_type:
                ore_types.add('R16')
            elif 'Common' in ore_type:
                ore_types.add('R8')
            elif 'Ubiquitous' in ore_type:
                ore_types.add('R4')
            else:
                ore_types.add('ABC')

            ore['total_quantity'] = ore['total_m3'] / ore['ore'].volume
            ore['total_value'] = float(ore['total_quantity']) * ore['ore'].get_history_avg(reprocess=True, reprocess_pct=.84, pct=0.9)
            ore['remaining_m3'] = ore['total_m3']
            ore['remaining_value'] = ore['total_value']
            extraction_ttl_value += ore['total_value']

        extraction_remaining_value = extraction_ttl_value

        structure.z_is_jackpot = False

        observer = MoonObserver.objects.filter(observer_id=structure.station_id).first()
        if observer is not None:
            for ore in ores:
                mining_log = MoonObserverEntry.objects.filter(observer_id=observer.id, last_updated__gte=min_date, type__name__endswith=ore['ore'].name)

                ore['mined_m3'] = 0
                ore['mined_qty'] = 0
                ore['mined_value'] = float()
                ore['is_jackpot'] = False

                for log in mining_log:
                    ore['is_jackpot'] = 'Twinkling' in log.type.name or 'Shining' in log.type.name \
                                        or 'Glowing' in log.type.name or 'Glistening' in log.type.name \
                                        or 'Shimmering' in log.type.name
                    ore['mined_m3'] += log.quantity * log.type.volume
                    ore['mined_quantity'] = log.quantity
                    ore['mined_value'] += float(log.quantity) * log.type.get_history_avg(reprocess=True, reprocess_pct=.84, pct=0.9)

                ore['remaining_m3'] = ore['total_m3'] - ore['mined_m3']
                ore['remaining_value'] = ore['ttl_value'] = ore['mined_value']

                if ore['is_jackpot']:
                    structure.z_is_jackpot = True

                extraction_remaining_m3 -= ore['mined_m3']
                extraction_remaining_value -= ore['mined_value']

        structure.z_config = cfg
        structure.z_ore_types = list(ore_types)
        structure.z_ores = ores
        structure.z_ttl_m3 = extraction_ttl_m3
        structure.z_ttl_value = extraction_ttl_value
        structure.z_remaining_m3 = extraction_remaining_m3
        structure.z_remaining_value = extraction_remaining_value

        structures.append(structure)

    out = render_page(
        'pgsus/extractions.html',
        dict(
            structures=structures,
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
        next_date_override = request.POST.get('next_date_override') or None
        chunk_time = request.POST.get('chunk_time') or None

        config = MoonConfig.objects.filter(structure_id=structure_id).first()
        if config is None:
            config = MoonConfig(
                structure_id=structure_id
            )

        config.next_date_override=next_date_override
        config.chunk_days = chunk_time

        config.save()

    waypoint_scope = CharacterApiScope.objects.filter(character_id=charid, scope='esi-ui.write_waypoint.v1').first()

    struct_services = StructureService.objects.filter(name='Moon Drilling', structure__station__corporation_id=corpid)

    struct_list = dict()

    for service in struct_services:
        structure = service.structure
        structure.z_online = service.state == 'online'
        structure.z_moon_info = MoonExtraction.objects.filter(structure_id=structure.station_id).first()

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

        if config is None or config.next_date_override is None \
                or config.next_date_override <= datetime.datetime.utcnow():
            if structure.z_moon_info is None:
                structure.z_next_chunk_time = datetime.datetime.utcnow().replace(second=0, microsecond=0) + datetime.timedelta(days=cycle_time)
            else:
                structure.z_next_chunk_time = structure.z_moon_info.chunk_arrival_time + datetime.timedelta(days=cycle_time)
        else:
            structure.z_next_chunk_time = config.next_date_override

        structure.z_cycle_time = cycle_time

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

    if 'comp_errors' in request.session:
        error_lines = request.session['comp_errors']
        moon_comps = request.session['moon_comps']
        request.session.delete('comp_errors')
        request.session.delete('moon_comps')

    out = render_page(
        'pgsus/refinerylist.html',
        dict(
            structures=struct_list,
            add_waypoint=waypoint_scope is not None,
            error_lines=error_lines,
            moon_comps=moon_comps,
        ),
        request,
    )

    return out



