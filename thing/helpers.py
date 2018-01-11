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

import re
from decimal import Decimal, ROUND_UP
from datetime import datetime

from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import stringfilter
from django.conf import settings
from django.utils.timesince import timesince

from jingo import register


@register.filter
def tablecols(data, cols):
    rows = []
    row = []
    index = 0
    for user in data:
        row.append(user)
        index = index + 1
        if index % cols == 0:
            rows.append(row)
            row = []
        # Still stuff missing?
    if len(row) > 0:
        for i in range(cols - len(row)):
            row.append([])
        rows.append(row)
    return rows

# Put commas in things
# http://code.activestate.com/recipes/498181-add-thousands-separator-commas-to-formatted-number/
re_digits_nondigits = re.compile(r'\d+|\D+')



@register.filter
@stringfilter
def commas(value, round_to=0, include_sign=False):
    try:
        value = float(value)
    except ValueError:
        return None
    if round_to is not None:
        value = round(value, round_to)

    if include_sign:
        format_str = '{0:+,.%df}'
    else:
        format_str = '{0:,.%df}'

    return (format_str % round_to).format(value)

@register.filter
def round_price(value):
    return round(value, 2)

@register.filter
def round_nodecimal(value):
    return round(value, 0)

@register.filter
def slugify(value):
    import unicodedata
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    try:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    except:
        pass
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)

def _commafy(s):
    r = []
    for i, c in enumerate(reversed(s)):
        if i and (not (i % 3)):
            r.insert(0, ',')
        r.insert(0, c)
    return ''.join(r)


@register.filter
def duration(s):
    """Turn a duration in seconds into a human readable string"""
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    parts = []
    if d:
        parts.append('%dd' % (d))
    if h:
        parts.append('%dh' % (h))
    if m:
        parts.append('%dm' % (m))
    if s:
        parts.append('%ds' % (s))

    return ' '.join(parts)


@register.filter
def duration_right(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    parts = []
    if d:
        parts.append('%dd' % (d))
    if h or d:
        parts.append('%02dh' % (h))
    if m or h or d:
        parts.append('%02dm' % (m))
    parts.append('%02ds' % (s))

    return ' '.join(parts)


@register.filter
def shortduration(s):
    """Turn a duration in seconds into a shorter human readable string"""
    return ' '.join(duration(s).split()[:2])


@register.filter
@stringfilter
def balance(s):
    """Do balance colouring (red for negative, green for positive)"""
    if s == '0':
        return s
    elif s.startswith('-'):
        return '<span class="neg">%s</span>' % (s)
    else:
        return '<span class="pos">%s</span>' % (s)


@register.filter
def balance_class(n):
    if n < 0:
        return 'neg'
    else:
        return 'pos'


roman_list = ['', 'I', 'II', 'III', 'IV', 'V']


@register.filter
def roman(num):
    if isinstance(num, str) or isinstance(num, unicode):
        return roman_list[int(num)]
    elif isinstance(num, int) or isinstance(num, long):
        return roman_list[num]
    else:
        return ''


MONTHS = [None, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']


@register.filter
def month_name(num):
    return MONTHS[num]


@register.filter
def date(d, f):
    return d.strftime(f)

@register.filter
def time(d):
    return d.strftime('%H:%M:%S')

@register.filter
def timeago(d, tz=True):
    fmt_str = '%Y-%m-%dT%H:%M:%S'
    if tz:
        fmt_str += '+0000'
    return '' if d is None else d.strftime(fmt_str)

# Shorten numbers to a human readable version
THOUSAND = 10 ** 3
TEN_THOUSAND = 10 ** 4
MILLION = 10 ** 6
BILLION = 10 ** 9


@register.filter
def lvl(value, best=5, better=4, append=""):
    value_fmt = "<b>%s</b>"
    if value >= best:
        cls = 'text-success'
    elif value >= better:
        cls = 'text-info'
    else:
        cls = 'text-danger'
        value_fmt = "%s"

    return '<span class="%s">%s%s</span>' % (cls, value_fmt % value, append)


@register.filter
def implant_lvl(value):
    return lvl(value, 5, 3, "%")


@register.filter
def pct_over(value):
    value_fmt = "<b>%s</b>"
    if value < 200:
        cls = 'txt-success'
    elif value < 400:
        cls = 'txt-info'
    else:
        cls = 'txt-danger'

    return '<span class="%s">%s%%</span>' % (cls, value_fmt % value)


@register.filter
def humanize(value, include_sign=False):
    if value is None or value == '':
        return '0'

    ret = ""

    if value >= BILLION or value <= -BILLION:
        v = Decimal(value) / BILLION
        ret = '%sB' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
    elif value >= MILLION or value <= -MILLION:
        v = Decimal(value) / MILLION
        if v >= 10:
            ret = '%sM' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
        else:
            ret = '%sM' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
    elif value >= TEN_THOUSAND or value <= -TEN_THOUSAND:
        v = Decimal(value) / THOUSAND
        ret = '%sK' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
    elif value >= THOUSAND or value <= -THOUSAND:
        ret = '%s' % (commas(Decimal(value).quantize(Decimal('1.'), rounding=ROUND_UP)))
    else:
        if isinstance(value, Decimal):
            ret = value.quantize(Decimal('.1'), rounding=ROUND_UP)
        else:
            ret = value

    if include_sign:
        if value > 0:
            ret = "+" + ret
        elif value < 0:
            ret = "-" + ret

    return ret




@register.filter
def spanif(value, arg):
    """Conditionally wrap some text in a span if it matches a condition. Ugh."""
    parts = arg.split()
    if len(parts) != 3:
        return value

    n = int(parts[2])
    if (parts[1] == '<' and value < n) or (parts[1] == '=' and value == n) or (parts[1] == '>' and value > n):
        return '<span class="%s">%s</span>' % (parts[0], value)
    else:
        return value


@register.function
def static(path):
    """Jinja2 filter version of staticfiles. Hopefully."""
    return staticfiles_storage.url(path)


@register.filter
def can_register(user):
    if (not settings.ALLOW_REGISTRATION) or user.is_authenticated():
        return False

    return True


@register.filter
def timeuntil(d):
    return timesince(datetime.utcnow(), d)
