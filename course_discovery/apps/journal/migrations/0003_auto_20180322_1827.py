# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-03-22 18:27
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20171004_1133'),
        ('journal', '0002_auto_20180322_1823'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='journal',
            options={},
        ),
        migrations.AlterUniqueTogether(
            name='journal',
            unique_together=set([('partner', 'uuid')]),
        ),
    ]
