# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0010_auto_20170417_0259'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricewatch',
            name='price_group',
            field=models.CharField(max_length=64, null=True),
            preserve_default=True,
        ),
    ]
