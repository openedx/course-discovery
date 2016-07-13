# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0004_program'),
    ]

    operations = [
        migrations.AlterField(
            model_name='program',
            name='uuid',
            field=models.UUIDField(verbose_name='UUID', editable=False, blank=True, unique=True, default=uuid.uuid4),
        ),
    ]
