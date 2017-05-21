# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0019_auto_20170519_1330'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='buyout',
            field=models.DecimalField(max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='collateral',
            field=models.DecimalField(max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='price',
            field=models.DecimalField(max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='reward',
            field=models.DecimalField(max_digits=20, decimal_places=2),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='contract',
            name='volume',
            field=models.DecimalField(max_digits=20, decimal_places=4),
            preserve_default=True,
        ),
    ]
