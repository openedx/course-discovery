# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0003_auto_20160523_1422'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='partner_short_code',
            field=models.CharField(max_length=8, null=True, default=None, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='partner_short_code',
            field=models.CharField(max_length=8, null=True, default=None, blank=True),
        ),
    ]
