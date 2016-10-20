# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0030_create_refresh_command_switches'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Estimated number of weeks needed to complete this course run.', null=True),
        ),
        migrations.AlterField(
            model_name='program',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(blank=True, help_text='This field is now deprecated (ECOM-6021).Estimated number of weeks needed to complete a course run belonging to this program.', null=True),
        ),
    ]
