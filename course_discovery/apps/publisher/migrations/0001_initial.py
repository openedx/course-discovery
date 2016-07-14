# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0006_auto_20160714_0512'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalStatus',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], max_length=15, db_index=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(db_constraint=False, to='course_metadata.CourseRun', related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
                ('updated_by', models.ForeignKey(db_constraint=False, to=settings.AUTH_USER_MODEL, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical status',
            },
        ),
        migrations.CreateModel(
            name='HistoricalWorkflowCourseRun',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(default=None, blank=True, help_text='SEO review on your course title and short description', null=True)),
                ('keywords', models.TextField(default=None, blank=True, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(default=None, blank=True, help_text='Please add any additional notes or special instructions for the course About Page.', null=True)),
                ('certificate_generation_exception', models.CharField(blank=True, help_text='If you have an exception request, please note it here.', null=True, max_length=255)),
                ('course_length', models.PositiveIntegerField(blank=True, help_text='Length of course, in number of weeks', null=True)),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(db_constraint=False, to='course_metadata.CourseRun', related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical workflow course run',
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], max_length=15, db_index=True)),
                ('course_run', models.OneToOneField(to='course_metadata.CourseRun', related_name='status_course_runs')),
                ('updated_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='updated_by_course_runs')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WorkflowCourseRun',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(default=None, blank=True, help_text='SEO review on your course title and short description', null=True)),
                ('keywords', models.TextField(default=None, blank=True, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(default=None, blank=True, help_text='Please add any additional notes or special instructions for the course About Page.', null=True)),
                ('certificate_generation_exception', models.CharField(blank=True, help_text='If you have an exception request, please note it here.', null=True, max_length=255)),
                ('course_length', models.PositiveIntegerField(blank=True, help_text='Length of course, in number of weeks', null=True)),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('course_run', models.OneToOneField(to='course_metadata.CourseRun', related_name='course_run_work_flow')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WorkflowProgram',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')], help_text='CourseRun association with any program.', max_length=15, db_index=True)),
                ('name', models.CharField(help_text='Name of the program.', max_length=255)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='workflowcourserun',
            name='program',
            field=models.ForeignKey(to='publisher.WorkflowProgram', related_name='program_work_flow'),
        ),
        migrations.AddField(
            model_name='historicalworkflowcourserun',
            name='program',
            field=models.ForeignKey(db_constraint=False, to='publisher.WorkflowProgram', related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
    ]
