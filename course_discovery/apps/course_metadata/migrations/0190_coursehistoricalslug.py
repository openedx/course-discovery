# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-16 17:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0197_make_slug_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseHistoricalSlug',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='url_slug_history', to='course_metadata.Course')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
