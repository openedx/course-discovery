# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_currency'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='currency',
            options={},
        ),
        migrations.AlterModelOptions(
            name='language',
            options={},
        ),
        migrations.AlterModelOptions(
            name='locale',
            options={},
        ),
        migrations.RemoveField(
            model_name='currency',
            name='created',
        ),
        migrations.RemoveField(
            model_name='currency',
            name='id',
        ),
        migrations.RemoveField(
            model_name='currency',
            name='modified',
        ),
        migrations.RemoveField(
            model_name='language',
            name='created',
        ),
        migrations.RemoveField(
            model_name='language',
            name='id',
        ),
        migrations.RemoveField(
            model_name='language',
            name='modified',
        ),
        migrations.RemoveField(
            model_name='locale',
            name='created',
        ),
        migrations.RemoveField(
            model_name='locale',
            name='id',
        ),
        migrations.RemoveField(
            model_name='locale',
            name='modified',
        ),
        migrations.AlterField(
            model_name='currency',
            name='iso_code',
            field=models.CharField(serialize=False, primary_key=True, max_length=3, unique=True),
        ),
        migrations.AlterField(
            model_name='language',
            name='iso_code',
            field=models.CharField(serialize=False, primary_key=True, max_length=2, unique=True),
        ),
        migrations.AlterField(
            model_name='locale',
            name='iso_code',
            field=models.CharField(serialize=False, primary_key=True, max_length=5, unique=True),
        ),
    ]
