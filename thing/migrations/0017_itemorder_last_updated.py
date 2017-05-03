# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0016_itemorder'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemorder',
            name='last_updated',
            field=models.DateTimeField(default=None),
            preserve_default=True,
        ),
    ]
