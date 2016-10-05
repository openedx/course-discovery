from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the reduced_program_data switch."""
    Switch = apps.get_model('waffle', 'Switch')

    Switch.objects.get_or_create(name='reduced_program_data', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the reduced_program_data switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='reduced_program_data').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
