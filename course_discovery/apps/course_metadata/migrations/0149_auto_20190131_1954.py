# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-01-31 19:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0148_degree_hubspot_lead_capture_form_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='degree',
            name='hubspot_lead_capture_form_id',
            field=models.CharField(blank=True, help_text='The Hubspot form ID for the lead capture form', max_length=128, null=True),
        ),
    ]
