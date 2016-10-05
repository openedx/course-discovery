# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('publisher', '0009_auto_20160929_1927'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='institution',
            field=models.ForeignKey(blank=True, related_name='publisher_courses_group', verbose_name='Institute that will be providing the course.', null=True, to='auth.Group'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='institution',
            field=models.ForeignKey(blank=True, related_name='+', db_constraint=False, null=True, to='auth.Group', on_delete=django.db.models.deletion.DO_NOTHING),
        ),
        migrations.AlterField(
            model_name='course',
            name='expected_learnings',
            field=models.TextField(blank=True, verbose_name='Expected Learnings', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='full_description',
            field=models.TextField(blank=True, verbose_name='Full Description', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(blank=True, related_name='publisher_courses', verbose_name='Level Type', null=True, to='course_metadata.LevelType', default=None),
        ),
        migrations.AlterField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(blank=True, verbose_name='Prerequisites', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='short_description',
            field=models.CharField(blank=True, verbose_name='Brief Description', max_length=255, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='language',
            field=models.ForeignKey(blank=True, related_name='publisher_course_runs', verbose_name='Content Language', null=True, to='ietf_language_tags.LanguageTag'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='expected_learnings',
            field=models.TextField(blank=True, verbose_name='Expected Learnings', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='full_description',
            field=models.TextField(blank=True, verbose_name='Full Description', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='prerequisites',
            field=models.TextField(blank=True, verbose_name='Prerequisites', default=None, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='short_description',
            field=models.CharField(blank=True, verbose_name='Brief Description', max_length=255, default=None, null=True),
        ),
    ]
