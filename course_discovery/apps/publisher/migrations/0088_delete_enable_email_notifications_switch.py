from django.db import migrations


def create_switch(apps, _schema_editor):
    """Create the enable_publisher_email_notifications switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='enable_publisher_email_notifications', defaults={'active': False})


def delete_switch(apps, _schema_editor):
    """Delete the enable_publisher_email_notifications switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='enable_publisher_email_notifications').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0087_remove_auto_create_in_studio'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(delete_switch, create_switch),
    ]
