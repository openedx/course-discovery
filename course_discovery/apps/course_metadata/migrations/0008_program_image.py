# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0007_auto_20160720_1749'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='image',
            field=models.ForeignKey(to='course_metadata.Image', blank=True, null=True, default=None),
        ),
    ]
