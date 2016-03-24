# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_language_locale'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('iso_code', models.CharField(max_length=2)),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
            },
        ),
    ]
