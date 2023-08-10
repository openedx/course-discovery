from django.db import migrations

from course_discovery.apps.publisher.constants import PARTNER_COORDINATOR_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME


def rename_group_to_project_coordinator(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    pc_group = Group.objects.get(name=PARTNER_COORDINATOR_GROUP_NAME)
    pc_group.name = PROJECT_COORDINATOR_GROUP_NAME
    pc_group.save()


def rename_group_to_partner_coordinator(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')

    pc_group = Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME)
    pc_group.name = PARTNER_COORDINATOR_GROUP_NAME
    pc_group.save()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0038_auto_20170223_0723'),
    ]

    operations = [
        migrations.RunPython(rename_group_to_project_coordinator, rename_group_to_partner_coordinator)
    ]
