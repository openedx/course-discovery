# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-02-07 13:14
from __future__ import unicode_literals

import stdimage.models
from django.db import migrations

from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0233_add_credit_value_to_program_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='programtype',
            name='logo_image',
            field=stdimage.models.StdImageField(blank=True, help_text='Please provide an image file with transparent background', null=True, upload_to=UploadToFieldNamePath(populate_from='name', path='media/program_types/logo_images/')),
        ),
    ]
