# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0012_freighterpricemodel_freightersystem'),
    ]

    operations = [
        migrations.AddField(
            model_name='freighterpricemodel',
            name='in_system_base',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='freighterpricemodel',
            name='in_system_collateral',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='freighterpricemodel',
            name='in_system_m3',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
    ]
