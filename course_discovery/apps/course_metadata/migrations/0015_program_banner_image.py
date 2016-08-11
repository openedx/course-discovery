# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import stdimage.utils
import stdimage.models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0014_auto_20160811_0436'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='banner_image',
            field=stdimage.models.StdImageField(upload_to=stdimage.utils.UploadToClassNameDirUUID(), blank=True, null=True),
        ),
    ]
