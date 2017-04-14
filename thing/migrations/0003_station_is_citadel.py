# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0002_auto_20160126_1128'),
    ]

    operations = [
        migrations.AddField(
            model_name='station',
            name='is_citadel',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
