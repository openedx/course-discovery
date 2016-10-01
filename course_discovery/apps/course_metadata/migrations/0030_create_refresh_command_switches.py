from django.db import migrations

NAMES = ('threaded_metadata_write', 'parallel_refresh_pipeline')


def create_switches(apps, schema_editor):
    """Create the threaded_metadata_write and parallel_refresh_pipeline switches."""
    Switch = apps.get_model('waffle', 'Switch')

    for name in NAMES:
        Switch.objects.get_or_create(name=name, defaults={'active': False})


def delete_switches(apps, schema_editor):
    """Delete the threaded_metadata_write and parallel_refresh_pipeline switches."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name__in=NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0029_auto_20160923_1306'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switches, reverse_code=delete_switches),
    ]
