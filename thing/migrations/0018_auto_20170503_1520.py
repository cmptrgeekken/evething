# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0017_itemorder_last_updated'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemorder',
            name='region',
            field=models.ForeignKey(default=None, to='thing.Region'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pricewatch',
            name='active',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
