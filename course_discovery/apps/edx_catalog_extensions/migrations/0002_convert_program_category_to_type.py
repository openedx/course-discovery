# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def set_program_types(apps, schema_editor):
    Program = apps.get_model('course_metadata', 'Program')
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    xseries_type = ProgramType.objects.get(name='XSeries')

    Program.objects.filter(category__iexact='xseries').update(type=xseries_type)


class Migration(migrations.Migration):
    dependencies = [
        ('edx_catalog_extensions', '0001_create_program_types'),
    ]

    operations = [
        migrations.RunPython(set_program_types, reverse_code=migrations.RunPython.noop)
    ]
