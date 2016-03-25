# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_currency'),
        ('course_metadata', '0003_auto_20160318_1900'),
    ]

    operations = [
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(max_length=255)),
                ('price', models.DecimalField(max_digits=8, decimal_places=2)),
                ('updgrade_deadline', models.DateTimeField()),
                ('credit_provider_key', models.CharField(max_length=255)),
                ('credit_hours', models.IntegerField()),
                ('currency', models.ForeignKey(to='core.Currency')),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='full_description',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='course',
            name='image',
            field=models.ForeignKey(to='course_metadata.Image', default=None, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(to='course_metadata.LevelType', default=None, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='short_description',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='course',
            name='title',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='course',
            name='video',
            field=models.ForeignKey(to='course_metadata.Video', default=None, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='announcment',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='effort',
            field=models.ForeignKey(to='course_metadata.Effort', null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='end',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='enrollment_period_end',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='enrollment_period_start',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='full_description',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='courserun',
            name='image',
            field=models.ForeignKey(to='course_metadata.Image', default=None, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='locale',
            field=models.ForeignKey(to='core.Locale', null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='pacing_type',
            field=models.ForeignKey(to='course_metadata.PacingType', null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='short_description',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='courserun',
            name='start',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='title',
            field=models.CharField(null=True, default=None, max_length=255),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video',
            field=models.ForeignKey(to='course_metadata.Video', default=None, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='description',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='organization',
            name='homepage_url',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(to='course_metadata.Image', null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='name',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='person',
            name='bio',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='person',
            name='name',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='person',
            name='profile_image',
            field=models.ForeignKey(to='course_metadata.Image', null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='title',
            field=models.CharField(null=True, max_length=255),
        ),
    ]
