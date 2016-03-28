# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_auto_20160315_1910'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('code', models.CharField(unique=True, primary_key=True, serialize=False, max_length=6)),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name_plural': 'Currencies',
            },
        ),
    ]
