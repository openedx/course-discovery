# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-04-24 18:30
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0170_courserun_go_live_date'),
    ]

    operations = [
        migrations.RenameField(
            model_name='courserun',
            old_name='go_live_date',
            new_name='publish_date',
        ),
    ]
