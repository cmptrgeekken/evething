# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0024_auto_20170620_1326'),
    ]

    operations = [
        migrations.CreateModel(
            name='StationOrder',
            fields=[
                ('order_id', models.BigIntegerField(serialize=False, primary_key=True)),
                ('volume_entered', models.IntegerField()),
                ('volume_remaining', models.IntegerField()),
                ('minimum_volume', models.IntegerField()),
                ('price', models.DecimalField(max_digits=20, decimal_places=2)),
                ('buy_order', models.BooleanField(default=False)),
                ('issued', models.DateTimeField(db_index=True)),
                ('expires', models.DateTimeField(db_index=True)),
                ('range', models.CharField(max_length=20, null=True)),
                ('item', models.ForeignKey(to='thing.Item')),
                ('station', models.ForeignKey(to='thing.Station')),
            ],
            options={
                'ordering': ('buy_order', 'item__name'),
            },
            bases=(models.Model,),
        ),
    ]
