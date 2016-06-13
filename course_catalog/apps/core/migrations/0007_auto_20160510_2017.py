# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_referral_tracking_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='referral_tracking_id',
            field=models.CharField(max_length=255, verbose_name='Referral Tracking ID', default='affiliate_partner'),
        ),
    ]
