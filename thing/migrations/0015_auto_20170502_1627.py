# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0014_auto_20170429_0932'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='freighterpricemodel',
            options={'ordering': ('sort_order',)},
        ),
        migrations.AddField(
            model_name='contractitem',
            name='calculated_price',
            field=models.DecimalField(null=True, max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
    ]
