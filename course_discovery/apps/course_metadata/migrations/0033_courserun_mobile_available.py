# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0032_auto_20161021_1636'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='mobile_available',
            field=models.BooleanField(default=False),
        ),
    ]
