# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django_extensions.db.fields
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0006_auto_20160714_0448'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalStatus',
            fields=[
                ('id', models.IntegerField(blank=True, db_index=True, verbose_name='ID', auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(db_index=True, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], max_length=15)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(blank=True, db_constraint=False, to='course_metadata.CourseRun', on_delete=django.db.models.deletion.DO_NOTHING, null=True, related_name='+')),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name='+')),
                ('updated_by', models.ForeignKey(blank=True, db_constraint=False, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.DO_NOTHING, null=True, related_name='+')),
            ],
            options={
                'verbose_name': 'historical status',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalWorkflowCourseRun',
            fields=[
                ('id', models.IntegerField(blank=True, db_index=True, verbose_name='ID', auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(blank=True, null=True, default=None, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(blank=True, default=None, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(blank=True, null=True, default=None, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(blank=True, null=True, max_length=255, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(blank=True, null=True, help_text='Length of course, in number of weeks')),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(blank=True, db_constraint=False, to='course_metadata.CourseRun', on_delete=django.db.models.deletion.DO_NOTHING, null=True, related_name='+')),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name='+')),
            ],
            options={
                'verbose_name': 'historical workflow course run',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(db_index=True, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], max_length=15)),
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
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(blank=True, null=True, default=None, help_text='SEO review on your course title and short description')),
                ('keywords', models.TextField(blank=True, default=None, help_text='Please add top 10 comma separated keywords for your course content')),
                ('notes', models.TextField(blank=True, null=True, default=None, help_text='Please add any additional notes or special instructions for the course About Page.')),
                ('certificate_generation_exception', models.CharField(blank=True, null=True, max_length=255, help_text='If you have an exception request, please note it here.')),
                ('course_length', models.PositiveIntegerField(blank=True, null=True, help_text='Length of course, in number of weeks')),
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
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(db_index=True, choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')], max_length=15, help_text='CourseRun association with any program.')),
                ('name', models.CharField(max_length=255, help_text='Name of the program.')),
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
            field=models.ForeignKey(blank=True, db_constraint=False, to='publisher.WorkflowProgram', on_delete=django.db.models.deletion.DO_NOTHING, null=True, related_name='+'),
        ),
    ]
