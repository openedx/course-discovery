# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-10-07 14:08
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0200_url_slug_history'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID'),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID'),
        ),
    ]
