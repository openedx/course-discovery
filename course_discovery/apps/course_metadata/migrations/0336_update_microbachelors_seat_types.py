"""
Migration to remove audit seat type from micro_bachelors program type.
"""
from django.db import migrations


def update_program_type(apps, schema_editor):  # pylint: disable=unused-argument
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    SeatType = apps.get_model('course_metadata', 'SeatType')

    micro_bachelors = ProgramType.objects.get(slug='microbachelors')
    verified_seat_type = SeatType.objects.get(slug='verified')

    # Set the applicable seat types for 'MicroBachelors' to only 'verified'
    micro_bachelors.applicable_seat_types.set([verified_seat_type])


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0335_migrateprogramslugconfiguration'),
    ]

    operations = [
        migrations.RunPython(update_program_type, migrations.RunPython.noop),
    ]
