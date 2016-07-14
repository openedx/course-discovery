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
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True, max_length=15)),
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
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
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
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
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
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True, max_length=15)),
                ('value', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'Person SocialNetwork',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='course_number',
            field=models.CharField(validators=[django.core.validators.RegexValidator(regex='[A-z0-9\\.]+x', code='invalid_course_number', message='Alphanumeric characters and dot (.) are allowed. With lower (x) at end.')], help_text='Course number denoted by .1, .2, etc. at the end of the course number before the `x`', blank=True, null=True, max_length=10),
        ),
        migrations.AddField(
            model_name='course',
            name='learner_testimonial',
            field=models.CharField(max_length=50, help_text='A quote from a learner in the course, demonstrating the value of taking the course', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='course_number',
            field=models.CharField(validators=[django.core.validators.RegexValidator(regex='[A-z0-9\\.]+x', code='invalid_course_number', message='Alphanumeric characters and dot (.) are allowed. With lower (x) at end.')], help_text='Course number denoted by .1, .2, etc. at the end of the course number before the `x`', blank=True, null=True, max_length=10),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='learner_testimonial',
            field=models.CharField(max_length=50, help_text='A quote from a learner in the course, demonstrating the value of taking the course', blank=True, null=True),
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
            name='languages',
            field=models.ManyToManyField(to='ietf_language_tags.LanguageTag', related_name='videos', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='personsocialnetwork',
            name='person',
            field=models.ForeignKey(to='course_metadata.Person', related_name='person_networks'),
        ),
        migrations.AddField(
            model_name='person',
            name='expertises',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Expertise', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='person',
            name='major_works',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.MajorWork', help_text=None, blank=True),
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
