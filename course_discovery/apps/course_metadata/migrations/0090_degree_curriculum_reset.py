# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-07-26 18:14
from __future__ import unicode_literals

import uuid

import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models

PAID_SEAT_TYPES = ('credit', 'verified',)
PROGRAM_TYPES = ('Masters',)


def add_program_types(apps, schema_editor):
    SeatType = apps.get_model('course_metadata', 'SeatType')
    ProgramType = apps.get_model('course_metadata', 'ProgramType')

    seat_types = SeatType.objects.filter(slug__in=PAID_SEAT_TYPES)

    for name in PROGRAM_TYPES:
        program_type, __ = ProgramType.objects.update_or_create(name=name)
        program_type.applicable_seat_types.clear()
        program_type.applicable_seat_types.add(*seat_types)
        program_type.save()


def drop_program_types(apps, schema_editor):
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    ProgramType.objects.filter(name__in=PROGRAM_TYPES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0089_auto_20180725_1602'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='degreecoursecurriculum',
            name='degree',
        ),
        migrations.RemoveField(
            model_name='degreeprogramcurriculum',
            name='degree',
        ),
        migrations.DeleteModel(
            name='DegreeMarketing',
        ),
        migrations.DeleteModel(
            name='Degree',
        ),
        migrations.RunPython(
            code=add_program_types,
            reverse_code=drop_program_types,
        ),
        migrations.CreateModel(
            name='Degree',
            fields=[
                ('program_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='course_metadata.Program')),
                ('application_deadline', models.CharField(help_text='String-based deadline field (e.g. FALL 2020)', max_length=255)),
                ('apply_url', models.CharField(blank=True, help_text='Callback URL to partner application flow', max_length=255)),
            ],
            options={
                'verbose_name_plural': 'degree marketing data',
            },
            bases=('course_metadata.program',),
        ),
        migrations.CreateModel(
            name='Curriculum',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('uuid', models.UUIDField(blank=True, default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID')),
                ('name', models.CharField(max_length=255)),
                ('course_curriculum', models.ManyToManyField(related_name='degree_course_curricula', through='course_metadata.DegreeCourseCurriculum', to='course_metadata.Course')),
                ('degree', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='curriculum', to='course_metadata.Degree')),
                ('program_curriculum', models.ManyToManyField(related_name='degree_program_curricula', through='course_metadata.DegreeProgramCurriculum', to='course_metadata.Program')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.AddField(
            model_name='degreecoursecurriculum',
            name='curriculum',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='course_metadata.Curriculum'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='degreeprogramcurriculum',
            name='curriculum',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='course_metadata.Curriculum'),
            preserve_default=False,
        ),
    ]
