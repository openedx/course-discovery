# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-09-11 11:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0115_increase_read_more_cutoff'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='short_description',
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]
