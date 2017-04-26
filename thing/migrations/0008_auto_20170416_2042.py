# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0007_pricewatch'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pricewatch',
            old_name='watch_active',
            new_name='active',
        ),
    ]
