# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-04-07 12:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0146_remove_log_queries_switch'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='invite_only',
            field=models.BooleanField(default=False),
        ),
    ]
