# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-02-13 09:14
from __future__ import unicode_literals

from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the publisher_history_widget_feature switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publisher_history_widget_feature', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the publisher_history_widget_feature switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='publisher_history_widget_feature').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0032_create_switch_for_comments'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
