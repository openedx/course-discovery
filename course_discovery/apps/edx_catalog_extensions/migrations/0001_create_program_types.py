from django.db import migrations

PAID_SEAT_TYPES = ('credit', 'professional', 'verified',)
PROGRAM_TYPES = ('XSeries', 'MicroMasters',)


def add_program_types(apps, schema_editor):
    SeatType = apps.get_model('course_metadata', 'SeatType')
    ProgramType = apps.get_model('course_metadata', 'ProgramType')

    seat_types = SeatType.objects.filter(slug__in=PAID_SEAT_TYPES)

    for name in PROGRAM_TYPES:
        program_type, __ = ProgramType.objects.update_or_create(name=name)
        program_type.applicable_seat_types.clear()
        program_type.applicable_seat_types.add(*seat_types)
        program_type.save()


def drop_program_types(apps, schema_editor):
    ProgramType = apps.get_model('course_metadata', 'ProgramType')
    ProgramType.objects.filter(name__in=PROGRAM_TYPES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0001_squashed_0033_courserun_mobile_available'),
    ]

    operations = [
        migrations.RunPython(add_program_types, drop_program_types)
    ]
