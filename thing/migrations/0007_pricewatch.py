# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0006_auto_20170407_1919'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceWatch',
            fields=[
                ('id', models.IntegerField(serialize=False, primary_key=True)),
                ('watch_active', models.BooleanField()),
                ('item', models.ForeignKey(related_name='watch_item', blank=True, to='thing.Item', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
