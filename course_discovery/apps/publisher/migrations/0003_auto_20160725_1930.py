# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0002_auto_20160721_1124'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(null=True, verbose_name='Partner Name', blank=True, related_name='publisher_courses', to='course_metadata.Organization'),
        ),
        migrations.AlterField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(null=True, default=None, blank=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='course',
            field=models.ForeignKey(to='publisher.Course', related_name='publisher_course_runs'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='micromasters_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(null=True, to='course_metadata.Person', blank=True, related_name='publisher_course_runs_staffed', help_text=None),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='xseries_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='prerequisites',
            field=models.TextField(null=True, default=None, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='micromasters_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='xseries_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
