# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-07-26 18:14
from __future__ import unicode_literals

from django.db import migrations

SEAT_TYPES = ('audit', 'verified',)
PROGRAM_TYPES = ('MicroBachelors',)


def add_program_types(apps, schema_editor):  # pylint: disable=unused-argument
    SeatType = apps.get_model('course_metadata', 'SeatType')
    ProgramType = apps.get_model('course_metadata', 'ProgramType')

    filtered_seat_types = SeatType.objects.filter(slug__in=SEAT_TYPES)

    for name in PROGRAM_TYPES:
        program_type, __ = ProgramType.objects.update_or_create(name=name)
        program_type.applicable_seat_types.clear()
        program_type.applicable_seat_types.add(*filtered_seat_types)
        program_type.save()


def drop_program_types(apps, schema_editor):  # pylint: disable=unused-argument
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    ProgramType.objects.filter(name__in=PROGRAM_TYPES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0191_remove_entitlement_expires'),
    ]

    operations = [
        migrations.RunPython(
            code=add_program_types,
            reverse_code=drop_program_types,
        ),
    ]