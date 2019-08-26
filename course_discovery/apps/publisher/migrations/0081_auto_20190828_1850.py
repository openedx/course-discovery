# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-28 18:50
from __future__ import unicode_literals

from django.db import migrations
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0080_populate_url_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='url_slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, editable=False, help_text='Leave this field blank to have the value generated automatically.', populate_from='title', unique=True),
        ),
    ]
