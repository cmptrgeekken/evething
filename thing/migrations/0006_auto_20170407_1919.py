# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0005_station_is_unknown'),
    ]

    operations = [
        migrations.AlterField(
            model_name='station',
            name='system',
            field=models.ForeignKey(blank=True, to='thing.System', null=True),
            preserve_default=True,
        ),
    ]
