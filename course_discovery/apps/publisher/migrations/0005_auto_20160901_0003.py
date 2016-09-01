# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import djchoices.choices


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0004_auto_20160810_0854'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='pacing_type',
            field=models.CharField(max_length=255, null=True, blank=True, choices=[('instructor_paced', 'Instructor-paced'), ('self_paced', 'Self-paced')], db_index=True, validators=[djchoices.choices.ChoicesValidator({'self_paced': 'Self-paced', 'instructor_paced': 'Instructor-paced'})]),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='pacing_type',
            field=models.CharField(max_length=255, null=True, blank=True, choices=[('instructor_paced', 'Instructor-paced'), ('self_paced', 'Self-paced')], db_index=True, validators=[djchoices.choices.ChoicesValidator({'self_paced': 'Self-paced', 'instructor_paced': 'Instructor-paced'})]),
        ),
    ]
