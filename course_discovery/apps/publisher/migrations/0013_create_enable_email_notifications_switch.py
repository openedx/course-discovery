from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the enable_publisher_email_notifications switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='enable_publisher_email_notifications', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the enable_publisher_email_notifications switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='enable_publisher_email_notifications').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0012_auto_20161020_0718'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
