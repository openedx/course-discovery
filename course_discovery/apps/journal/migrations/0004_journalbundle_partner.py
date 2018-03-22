# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-03-22 20:17
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20171004_1133'),
        ('journal', '0003_auto_20180322_1827'),
    ]

    operations = [
        migrations.AddField(
            model_name='journalbundle',
            name='partner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='core.Partner'),
            preserve_default=False,
        ),
    ]
