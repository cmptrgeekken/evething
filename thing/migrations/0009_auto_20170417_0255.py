# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0008_auto_20170416_2042'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='median',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='percentile',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_volume',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='std_dev',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
    ]
