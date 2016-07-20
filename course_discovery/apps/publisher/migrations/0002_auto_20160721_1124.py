# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='expected_learnings',
            field=models.TextField(blank=True, default=None, null=True, verbose_name="What you'll learn"),
        ),
        migrations.AlterField(
            model_name='course',
            name='full_description',
            field=models.TextField(blank=True, default=None, null=True, verbose_name='About this course'),
        ),
        migrations.AlterField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(blank=True, related_name='publisher_courses', to='course_metadata.LevelType', null=True, verbose_name='Course level', default=None),
        ),
        migrations.AlterField(
            model_name='course',
            name='number',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Course number'),
        ),
        migrations.AlterField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(blank=True, related_name='publisher_courses', to='course_metadata.Organization', verbose_name='Partner Name'),
        ),
        migrations.AlterField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(blank=True, default=None, null=True, verbose_name='Has prerequisites?'),
        ),
        migrations.AlterField(
            model_name='course',
            name='short_description',
            field=models.CharField(blank=True, max_length=255, default=None, null=True, verbose_name='Course subtitle'),
        ),
        migrations.AlterField(
            model_name='course',
            name='title',
            field=models.CharField(blank=True, max_length=255, default=None, null=True, verbose_name='Course title'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='expected_learnings',
            field=models.TextField(blank=True, default=None, null=True, verbose_name="What you'll learn"),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='full_description',
            field=models.TextField(blank=True, default=None, null=True, verbose_name='About this course'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='number',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Course number'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='prerequisites',
            field=models.TextField(blank=True, default=None, null=True, verbose_name='Has prerequisites?'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='short_description',
            field=models.CharField(blank=True, max_length=255, default=None, null=True, verbose_name='Course subtitle'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='title',
            field=models.CharField(blank=True, max_length=255, default=None, null=True, verbose_name='Course title'),
        ),
    ]
