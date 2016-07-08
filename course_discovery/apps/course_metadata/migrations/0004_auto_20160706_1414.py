# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import select_multiple_field.models
import sortedm2m.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0003_auto_20160523_1422'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRequirement',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(help_text='The user-facing display name for this requirement.', max_length=255, unique=True)),
                ('supported_seat_types', select_multiple_field.models.SelectMultipleField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('no-id-professional', 'Professional (No ID verification)'), ('credit', 'Credit')], max_length=255)),
                ('courses', models.ManyToManyField(to='course_metadata.Course')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Program',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid4, blank=True, editable=False, unique=True)),
                ('name', models.CharField(help_text='The user-facing display name for this Program.', max_length=255, unique=True)),
                ('subtitle', models.CharField(help_text='A brief, descriptive subtitle for the Program.', max_length=255, blank=True)),
                ('category', models.CharField(help_text='The category / type of Program.', choices=[('xseries', 'xseries')], max_length=32)),
                ('status', models.CharField(default='unpublished', help_text='The lifecycle status of this Program.', choices=[('unpublished', 'unpublished'), ('active', 'active'), ('retired', 'retired'), ('deleted', 'deleted')], max_length=24)),
                ('marketing_slug', models.CharField(help_text='Slug used to generate links to the marketing site', max_length=255, blank=True)),
                ('course_requirements', sortedm2m.fields.SortedManyToManyField(help_text=None, to='course_metadata.CourseRequirement')),
                ('organizations', models.ManyToManyField(to='course_metadata.Organization', blank=True)),
            ],
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='type',
            field=models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('no-id-professional', 'Professional (No ID verification)'), ('credit', 'Credit')], max_length=63),
        ),
        migrations.AlterField(
            model_name='seat',
            name='type',
            field=models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('no-id-professional', 'Professional (No ID verification)'), ('credit', 'Credit')], max_length=63),
        ),
        migrations.AlterIndexTogether(
            name='program',
            index_together=set([('status', 'category')]),
        ),
    ]
