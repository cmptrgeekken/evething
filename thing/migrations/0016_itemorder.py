# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0015_auto_20170502_1627'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemOrder',
            fields=[
                ('id', models.BigIntegerField(serialize=False, primary_key=True)),
                ('price', models.DecimalField(max_digits=14, decimal_places=2)),
                ('total_price', models.DecimalField(max_digits=17, decimal_places=2)),
                ('buy_order', models.BooleanField(default=False)),
                ('volume_entered', models.IntegerField()),
                ('volume_remaining', models.IntegerField()),
                ('minimum_volume', models.IntegerField()),
                ('issued', models.DateTimeField(db_index=True)),
                ('expires', models.DateTimeField(db_index=True)),
                ('range', models.CharField(max_length=20)),
                ('item', models.ForeignKey(to='thing.Item')),
                ('location', models.ForeignKey(to='thing.Station')),
            ],
            options={
                'ordering': ('buy_order', 'item__name'),
            },
            bases=(models.Model,),
        ),
    ]
