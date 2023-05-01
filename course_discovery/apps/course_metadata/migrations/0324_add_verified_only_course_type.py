from django.db import migrations


TYPE_NAME = 'Verified Only'
SLUG = 'verified'


def add_verified_only_types(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')
    Track = apps.get_model('course_metadata', 'Track')
    Mode = apps.get_model('course_metadata', 'Mode')
    SeatType = apps.get_model('course_metadata', 'SeatType')

    mode = Mode.objects.get(slug=SLUG)
    seat_type = SeatType.objects.get(slug=SLUG)
    run_type, _ = CourseRunType.objects.update_or_create(name=TYPE_NAME, slug=SLUG)
    run_type.tracks.set([Track.objects.get(mode=mode, seat_type=seat_type)])

    course_type, _ = CourseType.objects.update_or_create(name=TYPE_NAME, slug=SLUG)
    course_type.entitlement_types.set([seat_type])
    course_type.course_run_types.set([run_type])


def remove_verified_only_types(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')

    CourseType.objects.filter(slug=SLUG).delete()
    CourseRunType.objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0323_deduplicate_history_config_model'),
    ]

    operations = [
        migrations.RunPython(
            code=add_verified_only_types,
            reverse_code=remove_verified_only_types,
        ),
    ]
