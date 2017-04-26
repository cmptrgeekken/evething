# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0009_auto_20170417_0255'),
    ]

    operations = [
        migrations.RenameField(
            model_name='item',
            old_name='median',
            new_name='buy_median',
        ),
        migrations.RenameField(
            model_name='item',
            old_name='percentile',
            new_name='buy_percentile',
        ),
        migrations.RenameField(
            model_name='item',
            old_name='std_dev',
            new_name='buy_std_dev',
        ),
        migrations.AddField(
            model_name='item',
            name='buy_volume',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_median',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_percentile',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_std_dev',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
    ]
