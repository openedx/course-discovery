from django.db import migrations

SWITCH = 'publish_course_runs_to_marketing_site'


def create_switch(apps, schema_editor):
    """Create the publish_course_runs_to_marketing_site switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name=SWITCH, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the publish_course_runs_to_marketing_site switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=SWITCH).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0051_program_one_click_purchase_enabled'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
