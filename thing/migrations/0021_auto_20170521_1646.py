# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0020_auto_20170521_1133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='buyout',
            field=models.DecimalField(max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='collateral',
            field=models.DecimalField(max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='price',
            field=models.DecimalField(max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='reward',
            field=models.DecimalField(max_digits=15, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='volume',
            field=models.DecimalField(max_digits=16, decimal_places=4),
            preserve_default=True,
        ),
    ]
