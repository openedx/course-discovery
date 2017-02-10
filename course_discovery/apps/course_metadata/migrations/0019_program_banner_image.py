# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import stdimage.models
import stdimage.utils
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0018_auto_20160815_2252'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='banner_image',
            field=stdimage.models.StdImageField(upload_to=stdimage.utils.UploadToAutoSlugClassNameDir('uuid', path='/media/programs/banner_images'), null=True, blank=True),
        ),
    ]
