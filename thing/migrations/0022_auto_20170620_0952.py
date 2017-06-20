# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('thing', '0021_itemmaterial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='sso_refresh_token',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='industryjob',
            name='status',
            field=models.IntegerField(choices=[(1, b'Active'), (2, b'Paused (Facility Offline)'), (102, b'Cancelled'), (101, b'Delivered'), (103, b'Failed'), (999, b'Unknown')]),
            preserve_default=True,
        ),
    ]
