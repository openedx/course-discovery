# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django_extensions.db.fields
import django.db.models.deletion
import sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_currency'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ietf_language_tags', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbstractMediaModel',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('src', models.URLField(unique=True, max_length=255)),
                ('description', models.CharField(blank=True, null=True, max_length=255)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(unique=True, db_index=True, max_length=255)),
                ('title', models.CharField(default=None, blank=True, null=True, max_length=255)),
                ('short_description', models.CharField(default=None, blank=True, null=True, max_length=255)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CourseOrganization',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('relation_type', models.CharField(choices=[('owner', 'Owner'), ('sponsor', 'Sponsor')], max_length=63)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
        ),
        migrations.CreateModel(
            name='CourseRun',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(unique=True, max_length=255)),
                ('title_override', models.CharField(default=None, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", blank=True, max_length=255, null=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(default=None, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", blank=True, max_length=255, null=True)),
                ('full_description_override', models.TextField(default=None, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", blank=True, null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('course', models.ForeignKey(to='course_metadata.Course')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ExpectedLearningItem',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourse',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=255)),
                ('title', models.CharField(default=None, blank=True, null=True, max_length=255)),
                ('short_description', models.CharField(default=None, blank=True, null=True, max_length=255)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical course',
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRun',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=255)),
                ('title_override', models.CharField(default=None, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.", blank=True, max_length=255, null=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(default=None, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.", blank=True, max_length=255, null=True)),
                ('full_description_override', models.TextField(default=None, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", blank=True, null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Course', blank=True, null=True)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
                ('locale', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='ietf_language_tags.Locale', blank=True, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical course run',
            },
        ),
        migrations.CreateModel(
            name='HistoricalOrganization',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=255)),
                ('name', models.CharField(blank=True, null=True, max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(blank=True, null=True, max_length=255)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical organization',
            },
        ),
        migrations.CreateModel(
            name='HistoricalPerson',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=255)),
                ('name', models.CharField(blank=True, null=True, max_length=255)),
                ('title', models.CharField(blank=True, null=True, max_length=255)),
                ('bio', models.TextField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical person',
            },
        ),
        migrations.CreateModel(
            name='HistoricalSeat',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63)),
                ('price', models.DecimalField(max_digits=10, decimal_places=2)),
                ('upgrade_deadline', models.DateTimeField()),
                ('credit_provider', models.CharField(max_length=255)),
                ('credit_hours', models.IntegerField()),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.CourseRun', blank=True, null=True)),
                ('currency', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='core.Currency', blank=True, null=True)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical seat',
            },
        ),
        migrations.CreateModel(
            name='LevelType',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(unique=True, max_length=255)),
                ('name', models.CharField(blank=True, null=True, max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(blank=True, null=True, max_length=255)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PacingType',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(unique=True, max_length=255)),
                ('name', models.CharField(blank=True, null=True, max_length=255)),
                ('title', models.CharField(blank=True, null=True, max_length=255)),
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
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63)),
                ('price', models.DecimalField(max_digits=10, decimal_places=2)),
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
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SyllabusItem',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('value', models.CharField(max_length=255)),
                ('parent', models.ForeignKey(related_name='children', to='course_metadata.SyllabusItem', blank=True, null=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(to='course_metadata.AbstractMediaModel', parent_link=True, auto_created=True, primary_key=True, serialize=False)),
                ('height', models.IntegerField()),
                ('width', models.IntegerField()),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('abstractmediamodel_ptr', models.OneToOneField(to='course_metadata.AbstractMediaModel', parent_link=True, auto_created=True, primary_key=True, serialize=False)),
                ('type', models.CharField(max_length=255)),
                ('image', models.ForeignKey(to='course_metadata.Image')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
            bases=('course_metadata.abstractmediamodel',),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='pacing_type',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.PacingType', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='syllabus',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.SyllabusItem', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='level_type',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.LevelType', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='instructors',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Person', help_text=None, blank=True, related_name='courses_instructed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='locale',
            field=models.ForeignKey(to='ietf_language_tags.Locale', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='pacing_type',
            field=models.ForeignKey(to='course_metadata.PacingType', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Person', help_text=None, blank=True, related_name='courses_staffed'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='syllabus',
            field=models.ForeignKey(to='course_metadata.SyllabusItem', default=None, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='transcript_locales',
            field=models.ManyToManyField(to='ietf_language_tags.Locale', blank=True, related_name='transcript_courses'),
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
            field=models.ForeignKey(to='course_metadata.LevelType', default=None, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(to='course_metadata.Organization', blank=True, through='course_metadata.CourseOrganization'),
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
            field=models.ForeignKey(to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='profile_image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='logo_image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='video',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Video', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Image', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='video',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Video', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='image',
            field=models.ForeignKey(to='course_metadata.Image', default=None, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video',
            field=models.ForeignKey(to='course_metadata.Video', default=None, blank=True, null=True),
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
            field=models.ForeignKey(to='course_metadata.Image', default=None, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='video',
            field=models.ForeignKey(to='course_metadata.Video', default=None, blank=True, null=True),
        ),
    ]
