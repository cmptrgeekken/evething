# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0011_pricewatch_price_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='FreighterPriceModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=32)),
                ('in_region_collateral', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
                ('in_region_m3', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
                ('in_region_base', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
                ('cross_region_collateral', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
                ('cross_region_m3', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
                ('cross_region_base', models.DecimalField(default=0, max_digits=15, decimal_places=2)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FreighterSystem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('price_model', models.ForeignKey(to='thing.FreighterPriceModel')),
                ('system', models.ForeignKey(to='thing.System')),
            ],
            options={
                'ordering': ('system__name',),
            },
            bases=(models.Model,),
        ),
    ]
