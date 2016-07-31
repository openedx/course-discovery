# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20160730_2131'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='marketing_site_api_password',
            field=models.CharField(verbose_name='Marketing Site API Password', blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='partner',
            name='marketing_site_api_username',
            field=models.CharField(verbose_name='Marketing Site API Username', blank=True, max_length=255, null=True),
        ),
    ]
