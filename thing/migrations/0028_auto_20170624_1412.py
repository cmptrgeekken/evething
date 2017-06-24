# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0027_auto_20170620_1618'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemStationSeed',
            fields=[
                ('id', models.IntegerField(serialize=False, primary_key=True)),
                ('min_qty', models.IntegerField(default=0)),
                ('active', models.BooleanField(default=False)),
                ('item', models.ForeignKey(to='thing.Item')),
                ('station', models.ForeignKey(to='thing.Station')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='freighterpricemodel',
            name='is_thirdparty',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pricewatch',
            name='item',
            field=models.ForeignKey(default=0, to='thing.Item'),
            preserve_default=False,
        ),
    ]
