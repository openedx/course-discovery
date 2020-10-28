from django.db import migrations, models

# Contains the slug (unique identifier) and any fields that are not the default values
MODE_SLUGS_AND_DEFAULTS = (
    ('audit', {
        'name': 'Audit',
    }),
    ('professional', {
        'name': 'Professional Certificate',
        'is_id_verified': True,
        'certificate_type': 'professional',
        'payee': 'platform',
    }),
    ('verified', {
        'name': 'Verified',
        'is_id_verified': True,
        'certificate_type': 'verified',
        'payee': 'platform',
    }),
    ('credit', {
        'name': 'Credit',
        'is_id_verified': True,
        'is_credit_eligible': 1,
        'certificate_type': 'credit',
        'payee': 'platform',
    }),
)
# The slugs are identical across Mode and SeatType
TRACK_MODE_AND_SEAT_SLUGS = ('audit', 'professional', 'verified', 'credit',)
COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS = (
    ('Audit Only', 'audit', ['audit']),
    ('Professional Only', 'professional', ['professional']),
    ('Verified and Audit', 'verified-audit', ['audit', 'verified']),
    ('Credit', 'credit-verified-audit', ['audit', 'credit', 'verified']),
)
COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_NAMES = (
    ('Audit Only', 'audit', ['audit'], ['Audit Only']),
    ('Professional Only', 'professional', ['professional'], ['Professional Only']),
    ('Verified and Audit', 'verified-audit', ['verified'], ['Audit Only', 'Verified and Audit']),
    ('Credit', 'credit-verified-audit', ['verified'], ['Audit Only', 'Credit', 'Verified and Audit']),
)

def add_course_types_and_children(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')
    Track = apps.get_model('course_metadata', 'Track')
    Mode = apps.get_model('course_metadata', 'Mode')
    SeatType = apps.get_model('course_metadata', 'SeatType')

    for slug, defaults in MODE_SLUGS_AND_DEFAULTS:
        Mode.objects.update_or_create(slug=slug, defaults=defaults)
    for slug in TRACK_MODE_AND_SEAT_SLUGS:
        mode = Mode.objects.get(slug=slug)
        seat_type = SeatType.objects.get(slug=slug)
        Track.objects.update_or_create(mode=mode, seat_type=seat_type)
    for name, slug, track_slugs in COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS:
        tracks = []
        for track_slug in track_slugs:
            mode = Mode.objects.get(slug=track_slug)
            seat_type = SeatType.objects.get(slug=track_slug)
            tracks.append(Track.objects.get(mode=mode, seat_type=seat_type))
        run_type, _created = CourseRunType.objects.update_or_create(name=name, slug=slug)
        run_type.tracks.set(tracks)
    for course_name, slug, seat_type_slugs, run_type_names in COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_NAMES:
        course_type, _created = CourseType.objects.update_or_create(name=course_name, slug=slug)

        entitlement_types = [SeatType.objects.get(slug=seat_type_slug) for seat_type_slug in seat_type_slugs]
        course_type.entitlement_types.set(entitlement_types)

        run_types = [CourseRunType.objects.get(name=run_type_name) for run_type_name in run_type_names]
        course_type.course_run_types.set(run_types)

def drop_course_types_and_children(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')
    Track = apps.get_model('course_metadata', 'Track')
    Mode = apps.get_model('course_metadata', 'Mode')

    course_type_slugs = [slug for __, slug, __, __ in COURSE_TYPE_NAMES_SLUGS_SEAT_TYPE_SLUGS_AND_RUN_TYPE_NAMES]
    course_run_type_slugs = [slug for __, slug, __ in COURSE_RUN_TYPE_NAMES_SLUGS_AND_TRACK_SLUGS]
    mode_slugs = [slug for slug, __ in MODE_SLUGS_AND_DEFAULTS]

    CourseType.objects.filter(slug__in=course_type_slugs).delete()
    CourseRunType.objects.filter(slug__in=course_run_type_slugs).delete()

    modes = [Mode.objects.get(slug=slug) for slug in TRACK_MODE_AND_SEAT_SLUGS]
    Track.objects.filter(mode__in=modes).delete()

    Mode.objects.filter(slug__in=mode_slugs).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0204_auto_20191015_1955'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseruntype',
            name='slug',
            field=models.CharField(default=None, max_length=64, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='coursetype',
            name='slug',
            field=models.CharField(default=None, max_length=64, unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalcourseruntype',
            name='slug',
            field=models.CharField(db_index=True, default=None, max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalcoursetype',
            name='slug',
            field=models.CharField(db_index=True, default=None, max_length=64),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='historicalmode',
            name='payee',
            field=models.CharField(blank=True, choices=[('platform', 'Platform'), ('organization', 'Organization')], default='', help_text='Who gets paid for the course? Platform is the site owner, Organization is the school.', max_length=64),
        ),
        migrations.AlterField(
            model_name='mode',
            name='payee',
            field=models.CharField(blank=True, choices=[('platform', 'Platform'), ('organization', 'Organization')], default='', help_text='Who gets paid for the course? Platform is the site owner, Organization is the school.', max_length=64),
        ),
        migrations.RunPython(
            code=add_course_types_and_children,
            reverse_code=drop_course_types_and_children,
        ),
    ]
