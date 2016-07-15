# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0006_auto_20160714_0512'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunDetail',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(null=True, help_text='SEO review on your course title and short description', default=None, blank=True)),
                ('keywords', models.TextField(help_text='Please add top 10 comma separated keywords for your course content', default=None, blank=True)),
                ('notes', models.TextField(null=True, help_text='Please add any additional notes or special instructions for the course About Page.', default=None, blank=True)),
                ('certificate_generation_exception', models.CharField(null=True, max_length=255, help_text='If you have an exception request, please note it here.', blank=True)),
                ('course_length', models.PositiveIntegerField(null=True, help_text='Length of course, in number of weeks', blank=True)),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('course_run', models.OneToOneField(to='course_metadata.CourseRun', related_name='detail')),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRunDetail',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', auto_created=True, db_index=True, blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('is_re_run', models.BooleanField(default=True)),
                ('seo_review', models.TextField(null=True, help_text='SEO review on your course title and short description', default=None, blank=True)),
                ('keywords', models.TextField(help_text='Please add top 10 comma separated keywords for your course content', default=None, blank=True)),
                ('notes', models.TextField(null=True, help_text='Please add any additional notes or special instructions for the course About Page.', default=None, blank=True)),
                ('certificate_generation_exception', models.CharField(null=True, max_length=255, help_text='If you have an exception request, please note it here.', blank=True)),
                ('course_length', models.PositiveIntegerField(null=True, help_text='Length of course, in number of weeks', blank=True)),
                ('target_content', models.BooleanField(default=False)),
                ('priority', models.BooleanField(default=False)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(null=True, to='course_metadata.CourseRun', db_constraint=False, blank=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+')),
                ('history_user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
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
                ('id', models.IntegerField(verbose_name='ID', auto_created=True, db_index=True, blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=15, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], db_index=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(null=True, to='course_metadata.CourseRun', db_constraint=False, blank=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+')),
                ('history_user', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
                ('updated_by', models.ForeignKey(null=True, to=settings.AUTH_USER_MODEL, db_constraint=False, blank=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+')),
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
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=15, choices=[('draft', 'Draft'), ('review', 'Review'), ('published', 'Published')], db_index=True)),
                ('course_run', models.OneToOneField(to='course_metadata.CourseRun', related_name='status')),
                ('updated_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='status_updated_by')),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='WorkflowProgram',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(max_length=15, choices=[('xseries', 'XSeries'), ('micromasters', 'Micro-Masters')], db_index=True, help_text='CourseRun association with any program.')),
                ('name', models.CharField(max_length=255, help_text='Name of the program.')),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
        migrations.AddField(
            model_name='historicalcourserundetail',
            name='program',
            field=models.ForeignKey(null=True, to='publisher.WorkflowProgram', db_constraint=False, blank=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+'),
        ),
        migrations.AddField(
            model_name='courserundetail',
            name='program',
            field=models.ForeignKey(to='publisher.WorkflowProgram', related_name='program_work_flow'),
        ),
    ]
