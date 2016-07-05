# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import sortedm2m.fields
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('ietf_language_tags', '0002_language_tag_data_migration'),
        ('course_metadata', '0005_auto_20160713_0113'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(max_length=15, choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True)),
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
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MajorWork',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PersonSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(max_length=15, choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True)),
                ('value', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'Person SocialNetwork',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='learner_testimonial',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='A quote from a learner in the course, demonstrating the value of taking the course'),
        ),
        migrations.AddField(
            model_name='course',
            name='number',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='learner_testimonial',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='A quote from a learner in the course, demonstrating the value of taking the course'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='number',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x'),
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
            field=models.ManyToManyField(to='ietf_language_tags.LanguageTag', blank=True, related_name='transcript_videos'),
        ),
        migrations.AddField(
            model_name='personsocialnetwork',
            name='person',
            field=models.ForeignKey(to='course_metadata.Person', related_name='person_networks'),
        ),
        migrations.AddField(
            model_name='person',
            name='expertises',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Expertise', blank=True, related_name='person_expertise', help_text=None),
        ),
        migrations.AddField(
            model_name='person',
            name='major_works',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.MajorWork', blank=True, related_name='person_works', help_text=None),
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
