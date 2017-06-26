# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0028_auto_20170624_1412'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='item',
            name='buy_median',
        ),
        migrations.RemoveField(
            model_name='item',
            name='buy_percentile',
        ),
        migrations.RemoveField(
            model_name='item',
            name='buy_price',
        ),
        migrations.RemoveField(
            model_name='item',
            name='buy_std_dev',
        ),
        migrations.RemoveField(
            model_name='item',
            name='buy_volume',
        ),
        migrations.RemoveField(
            model_name='item',
            name='sell_median',
        ),
        migrations.RemoveField(
            model_name='item',
            name='sell_percentile',
        ),
        migrations.RemoveField(
            model_name='item',
            name='sell_price',
        ),
        migrations.RemoveField(
            model_name='item',
            name='sell_std_dev',
        ),
        migrations.RemoveField(
            model_name='item',
            name='sell_volume',
        ),
        migrations.AddField(
            model_name='item',
            name='buy_avg_price',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='buy_fivepct_price',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='buy_fivepct_volume',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='buy_total_volume',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_avg_price',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_fivepct_price',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_fivepct_volume',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='item',
            name='sell_total_volume',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
    ]
