# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

ADMIN_GROUP_NAME = 'Publisher Admins'


def create_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=ADMIN_GROUP_NAME)


def remove_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=ADMIN_GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0012_auto_20161020_0718'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(create_admin_group, remove_admin_group)
    ]
