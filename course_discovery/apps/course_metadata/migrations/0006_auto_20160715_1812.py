# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import django.core.validators
import sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [
        ('ietf_language_tags', '0002_language_tag_data_migration'),
        ('course_metadata', '0005_auto_20160713_0113'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(max_length=15, db_index=True, choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')])),
                ('value', models.CharField(max_length=500)),
                ('course_run', models.ForeignKey(to='course_metadata.CourseRun', related_name='course_run_networks')),
            ],
            options={
                'verbose_name_plural': 'CourseRun SocialNetwork',
            },
        ),
        migrations.CreateModel(
            name='Expertise',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MajorWork',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PersonSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(max_length=15, db_index=True, choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')])),
                ('value', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'Person SocialNetwork',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='course_number',
            field=models.CharField(validators=[django.core.validators.RegexValidator(message='Alphanumeric characters and dot (.) are allowed. With lower (x) at end.', regex='[A-z0-9\\.]+x', code='invalid_course_number')], max_length=10, help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='course',
            name='learner_testimonial',
            field=models.CharField(max_length=50, blank=True, help_text='A quote from a learner in the course, demonstrating the value of taking the course', null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='course_number',
            field=models.CharField(validators=[django.core.validators.RegexValidator(message='Alphanumeric characters and dot (.) are allowed. With lower (x) at end.', regex='[A-z0-9\\.]+x', code='invalid_course_number')], max_length=10, help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='learner_testimonial',
            field=models.CharField(max_length=50, blank=True, help_text='A quote from a learner in the course, demonstrating the value of taking the course', null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='email',
            field=models.EmailField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='username',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='email',
            field=models.EmailField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='username',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='video',
            name='transcript_languages',
            field=models.ManyToManyField(to='ietf_language_tags.LanguageTag', blank=True, null=True, related_name='transcript_videos'),
        ),
        migrations.AddField(
            model_name='personsocialnetwork',
            name='person',
            field=models.ForeignKey(to='course_metadata.Person', related_name='person_networks'),
        ),
        migrations.AddField(
            model_name='person',
            name='expertises',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Expertise', blank=True, help_text=None),
        ),
        migrations.AddField(
            model_name='person',
            name='major_works',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.MajorWork', blank=True, help_text=None),
        ),
        migrations.AlterUniqueTogether(
            name='personsocialnetwork',
            unique_together=set([('person', 'type')]),
        ),
        migrations.AlterUniqueTogether(
            name='courserunsocialnetwork',
            unique_together=set([('course_run', 'type')]),
        ),
    ]
