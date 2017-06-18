# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0020_auto_20170521_1133'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemMaterial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.IntegerField()),
                ('item', models.ForeignKey(related_name='item', to='thing.Item')),
                ('material', models.ForeignKey(related_name='item_material', to='thing.Item')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
