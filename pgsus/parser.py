from collections import defaultdict
from itertools import takewhile
from re import sub

import evepaste
from evepaste import parsers
from thing.models import Item


def parse(raw_paste):
    unique_items = set()
    results = []
    representative_kind = 'unknown'
    largest_kind_num = 0

    parser_list = list(evepaste.PARSER_TABLE) + [
        ('listing', listing_parser),
        ('heuristic', tryhard_parser),
    ]

    iterations = 0
    while iterations < 10:
        iterations += 1
        try:
            if not parser_list:
                break

            kind, result, bad_lines = evepaste.parse(raw_paste,
                                                     parsers=parser_list)

            if result:
                # Verify the results has some valid items and gather unique
                # items
                item_count = 0
                for item in iter_types(kind, result):
                    details = get_item_by_name(item['name'])
                    if details:
                        unique_items.add(details.id)
                        item_count += 1

                if item_count == 0:
                    # Narrow down the parser_list to those that didn't get a
                    # chance last time
                    used_parser_list = list(takewhile(lambda p: kind != p[0],
                                                      parser_list))
                    parser_list = parser_list[len(used_parser_list)+1:]
                    continue

                results.append([kind, result])

                # Determine if this is the representative type
                if item_count >= largest_kind_num:
                    representative_kind = kind
                    largest_kind_num = item_count

                raw_paste = '\n'.join(bad_lines)
            else:
                # We found zero results, we're done parsing
                break

            # We're finished parsing because we've consumed all of our data
            if not bad_lines:
                break

        except evepaste.Unparsable:
            if results:
                break
            else:
                raise

    return {'representative_kind': representative_kind,
            'results': results,
            'bad_lines': bad_lines,
            'unique_items': unique_items}


def listing_parser(lines):
    results = defaultdict(int)
    bad_lines = []
    lines = [line.strip() for line in lines]
    for line in lines:
        if get_item_by_name(line):
            results[line] += 1
        else:
            result, bad_line = parsers.parse_listing([line])
            for r in result:
                if get_item_by_name(r['name']):
                    results[r['name']] += r.get('quantity', 1)
                else:
                    bad_lines.append(line)
            for l in bad_line:
                bad_lines.append(l)

    return [{'name': name, 'quantity': quantity}
            for name, quantity in results.items()], bad_lines


def dscan_parser(lines):
    results, bad_lines = parsers.parse_dscan(lines)
    items = defaultdict(int)

    for result in results:
        items[result['name']] += 1

    return [{'name': name, 'quantity': quantity}
            for name, quantity in items.items()], bad_lines


def tryhard_parser(lines):
    results = defaultdict(int)
    bad_lines = []

    for line in lines:
        parts = [part.strip(', ') for part in line.split('\t')]
        if len(parts) == 1:
            parts = [part.strip(',\t ') for part in line.split('  ')]
            parts = [part for part in parts if part]

        if len(parts) == 1:
            parts = [part.strip(',') for part in line.split(' ')]
            parts = [part for part in parts if part]

        # This should only work for multi-part lines
        if len(parts) == 1:
            break

        combinations = [['name', 'quantity'],
                        [None, 'name', None, 'quantity'],
                        ['quantity', None, 'name'],
                        ['quantity', 'name'],
                        [None, 'name'],
                        ['name']]
        for combo in combinations:
            if len(combo) > len(parts):
                continue

            name = ''
            quantity = 1
            for i, part in enumerate(combo):
                if part == 'name':
                    if get_item_by_name(parts[i]):
                        name = parts[i]
                    else:
                        break
                elif part == 'quantity':
                    if int_convert(parts[i]):
                        quantity = int_convert(parts[i])
                    else:
                        break
            else:
                results[name] += quantity
                break
        else:
            # The above method failed. Now let's try splitting on spaces and
            # build each part until we find a valid type
            parts = [part.strip(',\t ') for part in line.split(' ')]
            for i in range(len(parts)):
                name = ' '.join(parts[:-i])
                if name and get_item_by_name(name):
                    results[name] += 1
                    break
            else:
                bad_lines.append(line)

    if not results:
        raise evepaste.Unparsable('No valid input')

    return [{'name': name, 'quantity': quantity}
            for name, quantity in results.items()], bad_lines


def iter_types(kind, result):
    if kind == 'bill_of_materials':
        for item in result:
            yield {'name': item['name'],
                   'quantity': item.get('you', item.get('quantity'))}
    elif kind == 'eft':
        yield {'name': result['ship'], 'quantity': 1}
        for item in result['modules']:
            yield item
            if item.get('ammo'):
                yield {'name': item['ammo'], 'quantity': 1}
    elif kind == 'killmail':
        yield {'name': result['victim']['destroyed'],
               'quantity': 1,
               'destroyed': True}
        for item in result['dropped']:
            item['dropped'] = True
            yield item
        for item in result['destroyed']:
            item['destroyed'] = True
            yield item
    elif kind == 'wallet':
        for item in result:
            if item.get('name'):
                yield item
    elif kind == 'chat':
        for item in result['items']:
            item['quantity'] = item.get('quantity', 1)
            yield item
    else:
        for item in result:
            item['quantity'] = item.get('quantity', 1)
            yield item

def get_item_by_name(name):
    return Item.objects.filter(
        name__iexact=name
    ).first()

def int_convert(s):
    try:
        return int(sub(r"[,'\. 'x]", '', s))
    except ValueError:
        return