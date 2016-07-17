# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0006_auto_20160715_1812'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunDetail',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('program_type', models.CharField(help_text='CourseRun associated with any program.', max_length=15, db_index=True, choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')])),
                ('program_name', models.CharField(help_text='Name of the program.', max_length=255)),
                ('seo_review', models.TextField(default=None, null=True, blank=True, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(default=None, help_text='Please add top 10 comma separated keywords for your course content', blank=True)),
                ('notes', models.TextField(default=None, null=True, blank=True, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(null=True, max_length=255, blank=True, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(null=True, blank=True, help_text='Length of course, in number of weeks')),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('course_run', models.OneToOneField(related_name='detail', to='course_metadata.CourseRun')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRunDetail',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', blank=True, db_index=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('program_type', models.CharField(help_text='CourseRun associated with any program.', max_length=15, db_index=True, choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')])),
                ('program_name', models.CharField(help_text='Name of the program.', max_length=255)),
                ('seo_review', models.TextField(default=None, null=True, blank=True, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(default=None, help_text='Please add top 10 comma separated keywords for your course content', blank=True)),
                ('notes', models.TextField(default=None, null=True, blank=True, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(null=True, max_length=255, blank=True, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(null=True, blank=True, help_text='Length of course, in number of weeks')),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(null=True, related_name='+', to='course_metadata.CourseRun', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True)),
                ('history_user', models.ForeignKey(null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical course run detail',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalStatus',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', blank=True, db_index=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=15, db_index=True, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')])),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(null=True, related_name='+', to='course_metadata.CourseRun', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True)),
                ('history_user', models.ForeignKey(null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(null=True, related_name='+', to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True)),
            ],
            options={
                'verbose_name': 'historical status',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=15, db_index=True, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')])),
                ('course_run', models.OneToOneField(related_name='status', to='course_metadata.CourseRun')),
                ('updated_by', models.ForeignKey(related_name='status_updated_by', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
    ]
