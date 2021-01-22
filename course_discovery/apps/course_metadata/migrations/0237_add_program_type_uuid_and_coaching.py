# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-02-25 13:45
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


def add_uuid_to_program_types(apps, schema_editor):
    program_type = apps.get_model('course_metadata', 'ProgramType')

    for obj in program_type.objects.all():
        obj.uuid = uuid.uuid4()
        obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0236_auto_20200225_1340'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalprogramtype',
            name='coaching_supported',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicalprogramtype',
            name='uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, verbose_name='UUID'),
        ),
        migrations.AddField(
            model_name='programtype',
            name='coaching_supported',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='programtype',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID', null=True),
        ),
        migrations.RunPython(add_uuid_to_program_types, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='programtype',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False, unique=True, null=False),
        ),
    ]
