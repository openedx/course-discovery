# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0003_auto_20160404_1734'),
    ]

    operations = [
        migrations.AlterField(
            model_name='video',
            name='image',
            field=models.ForeignKey(to='course_metadata.Image', null=True, blank=True),
        ),
    ]
