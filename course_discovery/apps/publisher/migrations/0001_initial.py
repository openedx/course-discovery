# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0006_auto_20160718_2118'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunDetail',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('program_type', models.CharField(max_length=15, help_text='CourseRun associated with any program.', choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')], db_index=True)),
                ('program_name', models.CharField(max_length=255, help_text='Name of the program.')),
                ('seo_review', models.TextField(default=None, blank=True, null=True, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(default=None, blank=True, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(default=None, blank=True, null=True, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(max_length=255, blank=True, null=True, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(blank=True, null=True, help_text='Length of course, in number of weeks')),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('course_run', models.OneToOneField(related_name='detail', to='course_metadata.CourseRun')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRunDetail',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', auto_created=True, blank=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('program_type', models.CharField(max_length=15, help_text='CourseRun associated with any program.', choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')], db_index=True)),
                ('program_name', models.CharField(max_length=255, help_text='Name of the program.')),
                ('seo_review', models.TextField(default=None, blank=True, null=True, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(default=None, blank=True, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(default=None, blank=True, null=True, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(max_length=255, blank=True, null=True, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(blank=True, null=True, help_text='Length of course, in number of weeks')),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(related_name='+', to='course_metadata.CourseRun', db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, null=True)),
                ('history_user', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical course run detail',
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalStatus',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', auto_created=True, blank=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=15, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], db_index=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(related_name='+', to='course_metadata.CourseRun', db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, null=True)),
                ('history_user', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True)),
                ('updated_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical status',
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=15, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], db_index=True)),
                ('course_run', models.OneToOneField(related_name='status', to='course_metadata.CourseRun')),
                ('updated_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='status_updated_by')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
    ]
