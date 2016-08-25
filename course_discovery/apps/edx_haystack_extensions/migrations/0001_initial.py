# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ElasticsearchBoostConfig',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('function_score', jsonfield.fields.JSONField(help_text='JSON string containing an elasticsearch function score config.', verbose_name='Function Score', default={'boost': 5.0, 'boost_mode': 'multiply', 'functions': [], 'score_mode': 'multiply'})),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
