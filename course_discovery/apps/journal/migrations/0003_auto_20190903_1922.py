# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-09-03 19:22


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0002_auto_20180904_2040'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='journal',
            name='currency',
        ),
        migrations.RemoveField(
            model_name='journal',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='journal',
            name='partner',
        ),
        migrations.RemoveField(
            model_name='journalbundle',
            name='applicable_seat_types',
        ),
        migrations.RemoveField(
            model_name='journalbundle',
            name='courses',
        ),
        migrations.RemoveField(
            model_name='journalbundle',
            name='journals',
        ),
        migrations.RemoveField(
            model_name='journalbundle',
            name='partner',
        ),
        migrations.DeleteModel(
            name='Journal',
        ),
        migrations.DeleteModel(
            name='JournalBundle',
        ),
    ]
