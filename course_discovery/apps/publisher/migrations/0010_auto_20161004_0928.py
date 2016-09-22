# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('publisher', '0009_auto_20160929_1927'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='institution',
            field=models.ForeignKey(verbose_name='Institute that will be providing the course.', null=True, related_name='publisher_courses_group', to='auth.Group', blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='institution',
            field=models.ForeignKey(null=True, related_name='+', db_constraint=False, to='auth.Group', on_delete=django.db.models.deletion.DO_NOTHING, blank=True),
        ),
    ]
