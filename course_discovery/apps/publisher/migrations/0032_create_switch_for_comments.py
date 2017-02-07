from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the publisher_comment_widget_feature switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='publisher_comment_widget_feature', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the publisher_comment_widget_feature switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='publisher_comment_widget_feature').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('publisher', '0031_courserunstate_coursestate_historicalcourserunstate_historicalcoursestate'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
