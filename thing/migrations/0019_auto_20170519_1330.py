# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0018_auto_20170503_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricewatch',
            name='price_pct',
            field=models.DecimalField(default=1, max_digits=18, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pricewatch',
            name='price_type',
            field=models.CharField(default=b'5day', max_length=8),
            preserve_default=True,
        ),
    ]
