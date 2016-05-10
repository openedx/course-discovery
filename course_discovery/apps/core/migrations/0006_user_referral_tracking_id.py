# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_populate_currencies'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='referral_tracking_id',
            field=models.CharField(max_length=255, default='affiliate_partner', verbose_name=''),
        ),
    ]
