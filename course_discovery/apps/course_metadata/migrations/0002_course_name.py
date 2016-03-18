# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='name',
            field=models.CharField(max_length=255, default='name'),
            preserve_default=False,
        ),
    ]
