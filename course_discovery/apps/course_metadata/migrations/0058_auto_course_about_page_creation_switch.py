from django.db import migrations


def create_switch(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='auto_course_about_page_creation', defaults={'active': False})


def delete_switch(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='auto_course_about_page_creation').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0057_auto_20170915_1528'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
