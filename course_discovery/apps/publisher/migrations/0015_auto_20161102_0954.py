# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0014_create_admin_group'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'permissions': (('view_course', 'Can view course'), ('partner_coordinator', 'partner coordinator'), ('reviewer', 'reviewer'), ('publisher', 'publisher')), 'get_latest_by': 'modified', 'ordering': ('-modified', '-created')},
        ),
    ]
