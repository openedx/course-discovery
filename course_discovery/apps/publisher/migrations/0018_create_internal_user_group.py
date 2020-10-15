from django.db import migrations

from course_discovery.apps.publisher.constants import INTERNAL_USER_GROUP_NAME


def create_internal_user_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=INTERNAL_USER_GROUP_NAME)


def remove_internal_user_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=INTERNAL_USER_GROUP_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0017_auto_20161201_1501'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(create_internal_user_group, remove_internal_user_group)
    ]
