# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import sortedm2m.fields
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_currency_language_locale'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AbstractMediaModel',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('src', models.URLField(max_length=255, unique=True)),
                ('description', models.CharField(null=True, max_length=255, blank=True)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True, db_index=True)),
                ('title', models.CharField(null=True, max_length=255, blank=True, default=None)),
                ('short_description', models.CharField(null=True, max_length=255, blank=True, default=None)),
                ('full_description', models.TextField(null=True, blank=True, default=None)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='CourseOrganization',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('relation_type', models.CharField(choices=[('owner', 'Owner'), ('sponsor', 'Sponsor')], max_length=63)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
        ),
        migrations.CreateModel(
            name='CourseRun',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('title_override', models.CharField(help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", null=True, max_length=255, blank=True, default=None)),
                ('start', models.DateTimeField(null=True, blank=True)),
                ('end', models.DateTimeField(null=True, blank=True)),
                ('enrollment_start', models.DateTimeField(null=True, blank=True)),
                ('enrollment_end', models.DateTimeField(null=True, blank=True)),
                ('announcement', models.DateTimeField(null=True, blank=True)),
                ('short_description_override', models.CharField(help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", null=True, max_length=255, blank=True, default=None)),
                ('full_description_override', models.TextField(help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", null=True, blank=True, default=None)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', null=True, blank=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', null=True, blank=True)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='ExpectedLearningItem',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourse',
            fields=[
                ('id', models.IntegerField(auto_created=True, db_index=True, verbose_name='ID', blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title', models.CharField(null=True, max_length=255, blank=True, default=None)),
                ('short_description', models.CharField(null=True, max_length=255, blank=True, default=None)),
                ('full_description', models.TextField(null=True, blank=True, default=None)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical course',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRun',
            fields=[
                ('id', models.IntegerField(auto_created=True, db_index=True, verbose_name='ID', blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title_override', models.CharField(help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", null=True, max_length=255, blank=True, default=None)),
                ('start', models.DateTimeField(null=True, blank=True)),
                ('end', models.DateTimeField(null=True, blank=True)),
                ('enrollment_start', models.DateTimeField(null=True, blank=True)),
                ('enrollment_end', models.DateTimeField(null=True, blank=True)),
                ('announcement', models.DateTimeField(null=True, blank=True)),
                ('short_description_override', models.CharField(help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", null=True, max_length=255, blank=True, default=None)),
                ('full_description_override', models.TextField(help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", null=True, blank=True, default=None)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', null=True, blank=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', null=True, blank=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Course', db_constraint=False, blank=True, related_name='+')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, related_name='+')),
                ('locale', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='core.Locale', db_constraint=False, blank=True, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical course run',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalOrganization',
            fields=[
                ('id', models.IntegerField(auto_created=True, db_index=True, verbose_name='ID', blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(null=True, max_length=255, blank=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('homepage_url', models.URLField(null=True, max_length=255, blank=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical organization',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalPerson',
            fields=[
                ('id', models.IntegerField(auto_created=True, db_index=True, verbose_name='ID', blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(null=True, max_length=255, blank=True)),
                ('title', models.CharField(null=True, max_length=255, blank=True)),
                ('bio', models.TextField(null=True, blank=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical person',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalSeat',
            fields=[
                ('id', models.IntegerField(auto_created=True, db_index=True, verbose_name='ID', blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField()),
                ('credit_provider', models.CharField(max_length=255)),
                ('credit_hours', models.IntegerField()),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.CourseRun', db_constraint=False, blank=True, related_name='+')),
                ('currency', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='core.Currency', db_constraint=False, blank=True, related_name='+')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical seat',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='LevelType',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(null=True, max_length=255, blank=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('homepage_url', models.URLField(null=True, max_length=255, blank=True)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='PacingType',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(null=True, max_length=255, blank=True)),
                ('title', models.CharField(null=True, max_length=255, blank=True)),
                ('bio', models.TextField(null=True, blank=True)),
                ('organizations', models.ManyToManyField(blank=True, to='course_metadata.Organization')),
            ],
            options={
                'verbose_name_plural': 'People',
            },
        ),
        migrations.CreateModel(
            name='Prerequisite',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField()),
                ('credit_provider', models.CharField(max_length=255)),
                ('credit_hours', models.IntegerField()),
                ('course_run', models.ForeignKey(to='course_metadata.CourseRun', related_name='seats')),
                ('currency', models.ForeignKey(to='core.Currency')),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SyllabusItem',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
                ('parent', models.ForeignKey(null=True, to='course_metadata.SyllabusItem', blank=True, related_name='children')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(primary_key=True, to='course_metadata.AbstractMediaModel', auto_created=True, parent_link=True, serialize=False)),
                ('height', models.IntegerField()),
                ('width', models.IntegerField()),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(primary_key=True, to='course_metadata.AbstractMediaModel', auto_created=True, parent_link=True, serialize=False)),
                ('type', models.CharField(max_length=255)),
                ('image', models.ForeignKey(to='course_metadata.Image')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
                'ordering': ('-modified', '-created'),
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='pacing_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.PacingType', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='syllabus',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.SyllabusItem', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='level_type',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.LevelType', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='instructors',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, to='course_metadata.Person', blank=True, related_name='courses_instructed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='locale',
            field=models.ForeignKey(null=True, to='core.Locale', blank=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='pacing_type',
            field=models.ForeignKey(null=True, to='course_metadata.PacingType', blank=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, to='course_metadata.Person', blank=True, related_name='courses_staffed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='syllabus',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.SyllabusItem'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='transcript_locales',
            field=models.ManyToManyField(to='core.Locale', blank=True, related_name='transcript_courses'),
        ),
        migrations.AddField(
            model_name='courseorganization',
            name='organization',
            field=models.ForeignKey(to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='course',
            name='expected_learning_items',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.ExpectedLearningItem'),
        ),
        migrations.AddField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.LevelType'),
        ),
        migrations.AddField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(through='course_metadata.CourseOrganization', blank=True, to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.ManyToManyField(blank=True, to='course_metadata.Prerequisite'),
        ),
        migrations.AddField(
            model_name='course',
            name='subjects',
            field=models.ManyToManyField(blank=True, to='course_metadata.Subject'),
        ),
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together=set([('course_run', 'type', 'currency', 'credit_provider')]),
        ),
        migrations.AddField(
            model_name='person',
            name='profile_image',
            field=models.ForeignKey(null=True, to='course_metadata.Image', blank=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(null=True, to='course_metadata.Image', blank=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='profile_image',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Image', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='logo_image',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Image', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='image',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Image', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='video',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Video', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='image',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Image', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='video',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='course_metadata.Video', db_constraint=False, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='image',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.Image'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.Video'),
        ),
        migrations.AlterUniqueTogether(
            name='courseorganization',
            unique_together=set([('course', 'relation_type', 'relation_type')]),
        ),
        migrations.AlterIndexTogether(
            name='courseorganization',
            index_together=set([('course', 'relation_type')]),
        ),
        migrations.AddField(
            model_name='course',
            name='image',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.Image'),
        ),
        migrations.AddField(
            model_name='course',
            name='video',
            field=models.ForeignKey(null=True, default=None, blank=True, to='course_metadata.Video'),
        ),
    ]
