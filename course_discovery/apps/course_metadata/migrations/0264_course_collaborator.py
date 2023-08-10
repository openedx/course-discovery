# Generated by Django 2.2.13 on 2020-07-13 19:00

import course_discovery.apps.course_metadata.utils
from django.db import migrations, models
import django_extensions.db.fields
import sortedm2m.fields
import stdimage.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0263_auto_20200709_1828'),
    ]

    operations = [
        migrations.CreateModel(
            name='Collaborator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('image', stdimage.models.StdImageField(blank=True, help_text='Add the collaborator image, please make sure its dimensions are 80x80px', null=True, upload_to=course_discovery.apps.course_metadata.utils.UploadToFieldNamePath(path='media/course/collaborator/image/', populate_from='uuid'))),
                ('name', models.CharField(default='', max_length=255)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='course',
            name='collaborators',
            field=sortedm2m.fields.SortedManyToManyField(blank=True, help_text=None, related_name='courses_collaborated', to='course_metadata.Collaborator'),
        ),
    ]
