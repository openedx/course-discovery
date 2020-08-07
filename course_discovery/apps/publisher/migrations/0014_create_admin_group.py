from django.db import migrations

from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME


def create_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=ADMIN_GROUP_NAME)


def remove_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=ADMIN_GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0013_create_enable_email_notifications_switch'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(create_admin_group, remove_admin_group)
    ]
