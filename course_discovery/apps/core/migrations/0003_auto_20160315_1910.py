# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_userthrottlerate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userthrottlerate',
            name='rate',
            field=models.CharField(help_text='The rate of requests to limit this user to. The format is specified by Django Rest Framework (see http://www.django-rest-framework.org/api-guide/throttling/).', max_length=50),
        ),
    ]
