# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0035_auto_20161103_2129'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='canonical_course_run',
            field=models.OneToOneField(null=True, default=None, blank=True, to='course_metadata.CourseRun', related_name='canonical_for_course'),
        ),
    ]
