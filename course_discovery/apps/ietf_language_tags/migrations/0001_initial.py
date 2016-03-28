# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Locale',
            fields=[
                ('id', models.CharField(primary_key=True, unique=True, max_length=50, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('language_code', models.CharField(max_length=3)),
            ],
        ),
    ]
