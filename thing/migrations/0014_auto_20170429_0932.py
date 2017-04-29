# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0013_auto_20170429_0802'),
    ]

    operations = [
        migrations.AddField(
            model_name='freighterpricemodel',
            name='max_collateral',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='freighterpricemodel',
            name='max_m3',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='freighterpricemodel',
            name='sort_order',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
    ]
