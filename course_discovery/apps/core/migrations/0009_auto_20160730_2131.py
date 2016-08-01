# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_partner'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='courses_api_url',
            field=models.URLField(null=True, verbose_name='Courses API URL', max_length=255, blank=True),
        ),
        migrations.AlterField(
            model_name='partner',
            name='ecommerce_api_url',
            field=models.URLField(null=True, verbose_name='E-Commerce API URL', max_length=255, blank=True),
        ),
        migrations.AlterField(
            model_name='partner',
            name='marketing_api_url',
            field=models.URLField(blank=True, null=True, max_length=255, verbose_name='Marketing Site API URL'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='marketing_url_root',
            field=models.URLField(blank=True, null=True, max_length=255, verbose_name='Marketing Site URL'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='organizations_api_url',
            field=models.URLField(null=True, verbose_name='Organizations API URL', max_length=255, blank=True),
        ),
        migrations.AlterField(
            model_name='partner',
            name='programs_api_url',
            field=models.URLField(blank=True, null=True, max_length=255, verbose_name='Programs API URL'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='short_code',
            field=models.CharField(unique=True, help_text='Convenient code/slug used to identify this Partner (e.g. for management commands.)', max_length=8, verbose_name='Short Code'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='social_auth_edx_oidc_key',
            field=models.CharField(null=True, max_length=255, verbose_name='OpenID Connect Key'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='social_auth_edx_oidc_secret',
            field=models.CharField(null=True, max_length=255, verbose_name='OpenID Connect Secret'),
        ),
        migrations.AlterField(
            model_name='partner',
            name='social_auth_edx_oidc_url_root',
            field=models.CharField(null=True, max_length=255, verbose_name='OpenID Connect URL'),
        ),
        migrations.RenameField(
            model_name='partner',
            old_name='social_auth_edx_oidc_key',
            new_name='oidc_key',
        ),
        migrations.RenameField(
            model_name='partner',
            old_name='social_auth_edx_oidc_secret',
            new_name='oidc_secret',
        ),
        migrations.RenameField(
            model_name='partner',
            old_name='social_auth_edx_oidc_url_root',
            new_name='oidc_url_root',
        ),
        migrations.RenameField(
            model_name='partner',
            old_name='marketing_api_url',
            new_name='marketing_site_api_url',
        ),
        migrations.RenameField(
            model_name='partner',
            old_name='marketing_url_root',
            new_name='marketing_site_url_root',
        ),
    ]
