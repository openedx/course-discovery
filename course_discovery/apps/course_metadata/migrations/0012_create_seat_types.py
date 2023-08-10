from django.db import migrations

SEAT_TYPES = ('Audit', 'Credit', 'Professional', 'Verified',)


def add_seat_types(apps, schema_editor):
    SeatType = apps.get_model('course_metadata', 'SeatType')

    for name in SEAT_TYPES:
        SeatType.objects.update_or_create(name=name)


def drop_seat_types(apps, schema_editor):
    SeatType = apps.get_model('course_metadata', 'SeatType')
    SeatType.objects.filter(name__in=SEAT_TYPES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0011_auto_20160805_1949'),
    ]

    operations = [
        migrations.RunPython(add_seat_types, drop_seat_types)
    ]
