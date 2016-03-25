# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0004_auto_20160324_1910'),
    ]

    operations = [
        migrations.RenameField(
            model_name='courseorganization',
            old_name='type',
            new_name='relation_type',
        ),
        migrations.RenameField(
            model_name='courserunperson',
            old_name='type',
            new_name='relation_type',
        ),
        migrations.RenameField(
            model_name='prerequisite',
            old_name='course',
            new_name='courses',
        ),
        migrations.AddField(
            model_name='person',
            name='organizations',
            field=models.ManyToManyField(to='course_metadata.Organization'),
        ),
    ]
