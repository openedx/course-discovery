# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0007_auto_20160905_1020'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='state',
            field=models.ForeignKey(related_name='publisher_course_runs_state', blank=True, to='publisher.State', null=True),
        ),
    ]
