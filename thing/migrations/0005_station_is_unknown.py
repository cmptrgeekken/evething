# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0004_auto_20170407_1903'),
    ]

    operations = [
        migrations.AddField(
            model_name='station',
            name='is_unknown',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
