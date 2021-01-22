# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-04-08 17:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0169_auto_20190404_1733'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='draft_version',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='_official_version', to='course_metadata.Course'),
        ),
        migrations.AlterField(
            model_name='courseentitlement',
            name='draft_version',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='_official_version', to='course_metadata.CourseEntitlement'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='draft_version',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='_official_version', to='course_metadata.CourseRun'),
        ),
        migrations.AlterField(
            model_name='seat',
            name='draft_version',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='_official_version', to='course_metadata.Seat'),
        ),
    ]
