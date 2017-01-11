from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the publisher_hide_features_for_pilot switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publisher_hide_features_for_pilot', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the publisher_hide_features_for_pilot switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='publisher_hide_features_for_pilot').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0025_auto_20170106_1830'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
