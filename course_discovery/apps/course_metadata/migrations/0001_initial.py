# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import sortedm2m.fields
import django.db.models.deletion
from django.conf import settings
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0004_currency'),
        ('ietf_language_tags', '0002_language_tag_data_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbstractMediaModel',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('src', models.URLField(max_length=255, unique=True)),
                ('description', models.CharField(max_length=255, blank=True, null=True)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True, db_index=True)),
                ('title', models.CharField(max_length=255, default=None, blank=True, null=True)),
                ('short_description', models.CharField(max_length=255, default=None, blank=True, null=True)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='CourseOrganization',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('relation_type', models.CharField(choices=[('owner', 'Owner'), ('sponsor', 'Sponsor')], max_length=63)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
        ),
        migrations.CreateModel(
            name='CourseRun',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('title_override', models.CharField(max_length=255, default=None, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", blank=True, null=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(max_length=255, default=None, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", blank=True, null=True)),
                ('full_description_override', models.TextField(default=None, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", blank=True, null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('pacing_type', models.CharField(choices=[('self_paced', 'Self-paced'), ('instructor_paced', 'Instructor-paced')], max_length=255, db_index=True, blank=True, null=True)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='ExpectedLearningItem',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourse',
            fields=[
                ('id', models.IntegerField(db_index=True, blank=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title', models.CharField(max_length=255, default=None, blank=True, null=True)),
                ('short_description', models.CharField(max_length=255, default=None, blank=True, null=True)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical course',
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRun',
            fields=[
                ('id', models.IntegerField(db_index=True, blank=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title_override', models.CharField(max_length=255, default=None, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", blank=True, null=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(max_length=255, default=None, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", blank=True, null=True)),
                ('full_description_override', models.TextField(default=None, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", blank=True, null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('pacing_type', models.CharField(choices=[('self_paced', 'Self-paced'), ('instructor_paced', 'Instructor-paced')], max_length=255, db_index=True, blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course', models.ForeignKey(db_constraint=False, to='course_metadata.Course', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+')),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
                ('language', models.ForeignKey(db_constraint=False, to='ietf_language_tags.LanguageTag', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical course run',
            },
        ),
        migrations.CreateModel(
            name='HistoricalOrganization',
            fields=[
                ('id', models.IntegerField(db_index=True, blank=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255, blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(max_length=255, blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical organization',
            },
        ),
        migrations.CreateModel(
            name='HistoricalPerson',
            fields=[
                ('id', models.IntegerField(db_index=True, blank=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255, blank=True, null=True)),
                ('title', models.CharField(max_length=255, blank=True, null=True)),
                ('bio', models.TextField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical person',
            },
        ),
        migrations.CreateModel(
            name='HistoricalSeat',
            fields=[
                ('id', models.IntegerField(db_index=True, blank=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField()),
                ('credit_provider', models.CharField(max_length=255)),
                ('credit_hours', models.IntegerField()),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(db_constraint=False, to='course_metadata.CourseRun', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+')),
                ('currency', models.ForeignKey(db_constraint=False, to='core.Currency', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+')),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical seat',
            },
        ),
        migrations.CreateModel(
            name='LevelType',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
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
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(max_length=255, blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(max_length=255, blank=True, null=True)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(max_length=255, blank=True, null=True)),
                ('title', models.CharField(max_length=255, blank=True, null=True)),
                ('bio', models.TextField(blank=True, null=True)),
                ('organizations', models.ManyToManyField(to='course_metadata.Organization', blank=True)),
            ],
            options={
                'verbose_name_plural': 'People',
            },
        ),
        migrations.CreateModel(
            name='Prerequisite',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
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
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
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
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
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
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
                ('parent', models.ForeignKey(to='course_metadata.SyllabusItem', null=True, blank=True, related_name='children')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(serialize=False, parent_link=True, to='course_metadata.AbstractMediaModel', primary_key=True, auto_created=True)),
                ('height', models.IntegerField(blank=True, null=True)),
                ('width', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(serialize=False, parent_link=True, to='course_metadata.AbstractMediaModel', primary_key=True, auto_created=True)),
                ('image', models.ForeignKey(to='course_metadata.Image')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='syllabus',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.SyllabusItem', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='level_type',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.LevelType', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='instructors',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Person', help_text=None, blank=True, related_name='courses_instructed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='language',
            field=models.ForeignKey(to='ietf_language_tags.LanguageTag', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Person', help_text=None, blank=True, related_name='courses_staffed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='syllabus',
            field=models.ForeignKey(default=None, null=True, to='course_metadata.SyllabusItem', blank=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='transcript_languages',
            field=models.ManyToManyField(to='ietf_language_tags.LanguageTag', blank=True, related_name='transcript_courses'),
        ),
        migrations.AddField(
            model_name='courseorganization',
            name='organization',
            field=models.ForeignKey(to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='course',
            name='expected_learning_items',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.ExpectedLearningItem', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(default=None, null=True, to='course_metadata.LevelType', blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(to='course_metadata.Organization', through='course_metadata.CourseOrganization', blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.ManyToManyField(to='course_metadata.Prerequisite', blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='subjects',
            field=models.ManyToManyField(to='course_metadata.Subject', blank=True),
        ),
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together=set([('course_run', 'type', 'currency', 'credit_provider')]),
        ),
        migrations.AddField(
            model_name='person',
            name='profile_image',
            field=models.ForeignKey(to='course_metadata.Image', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(to='course_metadata.Image', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='profile_image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='logo_image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='video',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Video', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='video',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Video', null=True, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='image',
            field=models.ForeignKey(default=None, null=True, to='course_metadata.Image', blank=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video',
            field=models.ForeignKey(default=None, null=True, to='course_metadata.Video', blank=True),
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
            field=models.ForeignKey(default=None, null=True, to='course_metadata.Image', blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='video',
            field=models.ForeignKey(default=None, null=True, to='course_metadata.Video', blank=True),
        ),
    ]
