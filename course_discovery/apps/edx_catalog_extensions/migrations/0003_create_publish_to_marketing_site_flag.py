from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the publish_program_to_marketing_site switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publish_program_to_marketing_site', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the publish_program_to_marketing_site switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='publish_program_to_marketing_site').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('edx_catalog_extensions', '0002_convert_program_category_to_type'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
