from django.db import migrations

from course_discovery.apps.publisher.constants import PARTNER_MANAGER_GROUP_NAME


def create_partner_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=PARTNER_MANAGER_GROUP_NAME)


def remove_partner_manager_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=PARTNER_MANAGER_GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0027_remove_old_permissions'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(create_partner_manager_group, remove_partner_manager_group)
    ]
