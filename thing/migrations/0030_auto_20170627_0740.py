# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0029_auto_20170626_1126'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pricehistory',
            name='date',
            field=models.DateField(db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='stationorder',
            name='buy_order',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='stationorder',
            name='price',
            field=models.DecimalField(max_digits=20, decimal_places=2, db_index=True),
            preserve_default=True,
        ),
    ]
