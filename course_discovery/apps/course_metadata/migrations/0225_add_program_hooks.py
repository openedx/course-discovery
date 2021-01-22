# -*- coding: utf-8 -*-
# Generated by Django 1.11.26 on 2019-12-09 12:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0224_fill_in_course_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalprogram',
            name='marketing_hook',
            field=models.CharField(blank=True, help_text='A brief hook for the marketing website', max_length=255),
        ),
        migrations.AddField(
            model_name='program',
            name='marketing_hook',
            field=models.CharField(blank=True, help_text='A brief hook for the marketing website', max_length=255),
        ),
    ]
