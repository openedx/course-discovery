from django.db import migrations


def delete_switch(apps, schema_editor):
    """Delete the reduced_program_data switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='reduced_program_data').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('waffle', '0001_initial'),
        ('api', '0001_create_reduced_program_data_switch'),
    ]

    operations = [
        migrations.RunPython(delete_switch, reverse_code=migrations.RunPython.noop),
    ]
