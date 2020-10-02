# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2016-12-13 10:57


import stdimage.models
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0038_seat_sku'),
    ]

    operations = [
        migrations.AddField(
            model_name='programtype',
            name='logo_image',
            field=stdimage.models.StdImageField(blank=True, help_text='Please provide an image file with transparent background', null=True, upload_to=UploadToFieldNamePath('name', path='media/program_types/logo_images')),
        ),
    ]
