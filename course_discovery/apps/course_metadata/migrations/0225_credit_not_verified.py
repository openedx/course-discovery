from django.db import migrations


def credit_is_not_verified(apps, _schema_editor):
    Mode = apps.get_model('course_metadata', 'Mode')
    Mode.objects.filter(slug='credit').update(is_id_verified=False)


def credit_is_verified(apps, _schema_editor):
    Mode = apps.get_model('course_metadata', 'Mode')
    Mode.objects.filter(slug='credit').update(is_id_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0224_add_program_hooks'),
    ]

    operations = [
        migrations.RunPython(
            credit_is_not_verified,
            credit_is_verified,
        ),
    ]
