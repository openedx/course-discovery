# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2017-01-26 13:31


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_squashed_0011_auto_20161101_2207'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='studio_url',
            field=models.URLField(blank=True, max_length=255, null=True, verbose_name='Studio URL'),
        ),
    ]
