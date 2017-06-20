# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0025_stationorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='stationorder',
            name='last_updated',
            field=models.DateTimeField(null=True, db_index=True),
            preserve_default=True,
        ),
    ]
