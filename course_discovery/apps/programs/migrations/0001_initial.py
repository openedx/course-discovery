# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0003_auto_20160523_1422'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRequirement',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('key', models.CharField(help_text="The 'course' part of course_keys associated with this course requirement, for example 'DemoX' in 'edX/DemoX/Demo_Course'.", max_length=64)),
                ('display_name', models.CharField(help_text='The display name of this course requirement.', max_length=128)),
                ('organization', models.ForeignKey(to='course_metadata.Organization')),
                ('programs', models.ManyToManyField(to='course_metadata.Seat')),
            ],
        ),
        migrations.CreateModel(
            name='Program',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('external_id', models.IntegerField()),
                ('name', models.CharField(unique=True, help_text='The user-facing display name for this Program.', max_length=255)),
                ('subtitle', models.CharField(blank=True, help_text='A brief, descriptive subtitle for the Program.', max_length=255)),
                ('category', models.CharField(help_text='The category / type of Program.', max_length=32, choices=[('xseries', 'xseries')])),
                ('status', models.CharField(blank=True, help_text='The lifecycle status of this Program.', max_length=24, choices=[('unpublished', 'unpublished'), ('active', 'active'), ('retired', 'retired'), ('deleted', 'deleted')], default='unpublished')),
                ('marketing_slug', models.CharField(blank=True, help_text='Slug used to generate links to the marketing site', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='ProgramCourseRequirement',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('position', models.IntegerField()),
                ('course_requirement', models.ForeignKey(to='programs.CourseRequirement')),
                ('program', models.ForeignKey(to='programs.Program')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='ProgramOrganization',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('organization', models.ForeignKey(to='course_metadata.Organization')),
                ('program', models.ForeignKey(to='programs.Program')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AlterIndexTogether(
            name='program',
            index_together=set([('status', 'category')]),
        ),
        migrations.AlterUniqueTogether(
            name='programcourserequirement',
            unique_together=set([('program', 'position')]),
        ),
        migrations.AlterUniqueTogether(
            name='courserequirement',
            unique_together=set([('organization', 'key')]),
        ),
    ]
