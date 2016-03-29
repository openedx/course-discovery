# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='LanguageTag',
            fields=[
                ('id', models.CharField(serialize=False, max_length=50, primary_key=True)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
    ]
