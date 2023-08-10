from django.db import migrations

from course_discovery.apps.publisher.constants import (
    PARTNER_COORDINATOR_GROUP_NAME, PUBLISHER_GROUP_NAME, REVIEWER_GROUP_NAME
)

GROUPS = [PARTNER_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME, PUBLISHER_GROUP_NAME]


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    for group in GROUPS:
        Group.objects.get_or_create(name=group)


def remove_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    for group in GROUPS:
        Group.objects.filter(name=group).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0018_create_internal_user_group'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups)
    ]
