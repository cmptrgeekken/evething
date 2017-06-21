# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0026_stationorder_last_updated'),
    ]

    operations = [
        migrations.CreateModel(
            name='StationOrderUpdater',
            fields=[
                ('order_id', models.BigIntegerField(serialize=False, primary_key=True)),
                ('volume_remaining', models.IntegerField()),
                ('price', models.DecimalField(max_digits=20, decimal_places=2)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='stationorder',
            name='times_updated',
            field=models.IntegerField(null=True),
            preserve_default=True,
        ),
    ]
