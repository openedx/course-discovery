from django.db import migrations, models

# Contains the slug (unique identifier) and any fields that are not the default-model values
MODE_SLUGS_AND_DEFAULTS = (
    ('honor', {
        'name': 'Honor',
        'certificate_type': 'honor',
    }),
)
# The slugs are identical across Mode and SeatType
TRACK_MODE_AND_SEAT_SLUGS = ('honor',)
COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS = (
    ('Honor Only', 'honor', ['honor']),
    ('Verified and Honor', 'verified-honor', ['honor', 'verified']),
    ('Credit with Honor', 'credit-verified-honor', ['credit', 'honor', 'verified']),
)
COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_SLUGS = (
    ('Honor Only', 'honor', [], ['honor']),
    ('Verified and Honor', 'verified-honor', ['verified'], ['honor', 'verified-honor']),
    ('Credit with Honor', 'credit-verified-honor', ['verified'], ['honor', 'verified-honor', 'credit-verified-honor']),
)

def add_honor_course_type_and_children(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')
    Track = apps.get_model('course_metadata', 'Track')
    Mode = apps.get_model('course_metadata', 'Mode')
    SeatType = apps.get_model('course_metadata', 'SeatType')

    for slug, defaults in MODE_SLUGS_AND_DEFAULTS:
        Mode.objects.get_or_create(slug=slug, defaults=defaults)
    for slug in TRACK_MODE_AND_SEAT_SLUGS:
        mode = Mode.objects.get(slug=slug)
        seat_type, _created = SeatType.objects.get_or_create(slug=slug, defaults={'name': slug.capitalize()})
        Track.objects.get_or_create(mode=mode, seat_type=seat_type)
    for name, slug, track_slugs in COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS:
        tracks = []
        for track_slug in track_slugs:
            mode = Mode.objects.get(slug=track_slug)
            seat_type = SeatType.objects.get(slug=track_slug)
            tracks.append(Track.objects.get(mode=mode, seat_type=seat_type))
        run_type, _created = CourseRunType.objects.get_or_create(slug=slug, defaults={'name': name})
        run_type.tracks.set(tracks)
    for course_name, slug, seat_type_slugs, run_type_slugs in COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_SLUGS:
        course_type, _created = CourseType.objects.get_or_create(slug=slug, defaults={'name': course_name})

        entitlement_types = [SeatType.objects.get(slug=seat_type_slug) for seat_type_slug in seat_type_slugs]
        course_type.entitlement_types.set(entitlement_types)

        run_types = [CourseRunType.objects.get(slug=run_type_slug) for run_type_slug in run_type_slugs]
        course_type.course_run_types.set(run_types)

def drop_honor_course_type_and_children(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')
    Track = apps.get_model('course_metadata', 'Track')
    Mode = apps.get_model('course_metadata', 'Mode')

    course_type_slugs = [slug for __, slug, __, __ in COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_SLUGS]
    course_run_type_slugs = [slug for __, slug, __ in COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS]
    mode_slugs = [slug for slug, __ in MODE_SLUGS_AND_DEFAULTS]

    CourseType.objects.filter(slug__in=course_type_slugs).delete()
    CourseRunType.objects.filter(slug__in=course_run_type_slugs).delete()

    modes = [Mode.objects.get(slug=slug) for slug in TRACK_MODE_AND_SEAT_SLUGS]
    Track.objects.filter(mode__in=modes).delete()

    Mode.objects.filter(slug__in=mode_slugs).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0250_auto_20200518_2054'),
    ]

    operations = [
        migrations.RunPython(
            code=add_honor_course_type_and_children,
            reverse_code=drop_honor_course_type_and_children,
        ),
    ]
