# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0024_auto_20160901_1426'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='end',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='enrollment_end',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='end',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='enrollment_end',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
