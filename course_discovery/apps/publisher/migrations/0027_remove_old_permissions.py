from django.db import migrations


def remove_permissions(apps, schema_editor):
    # Few permissions renamed but remains in db. Removing them now.
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    OrganizationExtension = apps.get_model('publisher', 'OrganizationExtension')

    org_ext_content_type = ContentType.objects.get_for_model(OrganizationExtension)
    Permission.objects.filter(
        content_type=org_ext_content_type, codename__in=['view_course_run', 'edit_course_run']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0026_create_switch_hide_features_for_pilot'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.RunPython(remove_permissions, reverse_code=migrations.RunPython.noop)
    ]
