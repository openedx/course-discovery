# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0002_auto_20160727_1234'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(blank=True, to='course_metadata.Organization', verbose_name='Partner Name', related_name='publisher_courses', null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='primary_subject',
            field=models.ForeignKey(null=True, default=None, to='course_metadata.Subject', related_name='publisher_courses_primary', blank=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='secondary_subject',
            field=models.ForeignKey(null=True, default=None, to='course_metadata.Subject', related_name='publisher_courses_secondary', blank=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='tertiary_subject',
            field=models.ForeignKey(null=True, default=None, to='course_metadata.Subject', related_name='publisher_courses_tertiary', blank=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='course',
            field=models.ForeignKey(to='publisher.Course', related_name='publisher_course_runs'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='micromasters_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.Person', null=True, related_name='publisher_course_runs_staffed'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='xseries_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='micromasters_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='xseries_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
