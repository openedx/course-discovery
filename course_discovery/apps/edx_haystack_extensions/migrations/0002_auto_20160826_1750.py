# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import jsonfield.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('edx_haystack_extensions', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='elasticsearchboostconfig',
            name='function_score',
            field=jsonfield.fields.JSONField(verbose_name='Function Score', help_text='JSON string containing an elasticsearch function score config.', default={'boost_mode': 'multiply', 'boost': 1.0, 'functions': [], 'score_mode': 'multiply'}),
        ),
    ]
