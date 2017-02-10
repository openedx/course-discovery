# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20160510_2017'),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=128, unique=True)),
                ('short_code', models.CharField(max_length=8, unique=True)),
                ('courses_api_url', models.URLField(max_length=255, null=True)),
                ('ecommerce_api_url', models.URLField(max_length=255, null=True)),
                ('organizations_api_url', models.URLField(max_length=255, null=True)),
                ('programs_api_url', models.URLField(max_length=255, null=True)),
                ('marketing_api_url', models.URLField(max_length=255, null=True)),
                ('marketing_url_root', models.URLField(max_length=255, null=True)),
                ('social_auth_edx_oidc_url_root', models.CharField(max_length=255, null=True)),
                ('social_auth_edx_oidc_key', models.CharField(max_length=255, null=True)),
                ('social_auth_edx_oidc_secret', models.CharField(max_length=255, null=True)),
            ],
            options={
                'verbose_name': 'Partner',
                'verbose_name_plural': 'Partners',
            },
        ),
    ]
