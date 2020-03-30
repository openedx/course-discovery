"""
Adds the view permission for catalogs if it doesn't already exist.

This is added by default for Django 2.1+, but this is included for backwards compatibility.
"""
from __future__ import unicode_literals
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogs', '0002_catalog_include_archived'),
    ]

    def create_view_permission(apps, schema_editor):
        # Django 2.1 creates these views by default, so this ensures we don't violate uniqueness constraints.
        try:
            content_type = ContentType.objects.get(app_label="catalogs", model="catalog")
            if not Permission.objects.filter(codename='view_catalog').exists():
                Permission.objects.get_or_create(
                    codename='view_catalog',
                    name='Can view catalog',
                    content_type=content_type,
                )
        except ContentType.DoesNotExist:
            pass

    def destroy_view_permission(apps, schema_editor):
        try:
            permission = Permission.objects.get(codename='view_catalog')
            permission.delete()
        except Permission.DoesNotExist:
            pass

    operations = [
        migrations.RunPython(code=create_view_permission, reverse_code=destroy_view_permission)
    ]
