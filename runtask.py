#!/usr/bin/env python
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

import cPickle
import os
import sys
import time

from decimal import Decimal, InvalidOperation

# Set up our environment and import settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'evething.settings'
import django
django.setup()
from django.db import connections, transaction
from thing.tasks import EsiCharacterRoles, EsiContracts, EsiMoonExtraction, EsiMoonObserver, EsiNotifications, EsiStructures, EsiAssets, HistoryUpdater, FixNames, PriceUpdater

from thing.models import *  # NOPEP8
import sys


if __name__ == '__main__':
    libs = set(sys.argv[1:])

    to_run = []

    if 'assets' in libs:
        to_run.append(EsiAssets())

    if 'contracts' in libs:
        to_run.append(EsiContracts())

    if 'moonobserver' in libs:
        to_run.append(EsiMoonObserver())

    if 'moonextract' in libs:
        to_run.append(EsiMoonExtraction())

    if 'names' in libs:
        to_run.append(FixNames())

    if 'roles' in libs:
        to_run.append(EsiCharacterRoles())

    if 'notifications' in libs:
        to_run.append(EsiNotifications())

    if 'structures' in libs:
        to_run.append(EsiStructures())

    if 'price' in libs:
        to_run.append(PriceUpdater())

    if 'history' in libs:
        to_run.append(HistoryUpdater())

    for run in to_run:
        print('Running %s...' % run.__name__)
        run.run()

