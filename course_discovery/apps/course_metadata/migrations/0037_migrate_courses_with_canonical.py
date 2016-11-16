from django.db import migrations

from course_discovery.apps.course_metadata.choices import CourseRunStatus


def create_canonical(apps, schema_editor):
    """Create the canonical course run associations."""
    Course = apps.get_model('course_metadata', 'Course')

    courses = Course.objects.prefetch_related('course_runs').all()
    for course in courses:
        course_runs = course.course_runs.all().order_by('-start')
        published_course_runs = course_runs.filter(status=CourseRunStatus.Published)
        if published_course_runs:
            # If there is a published course_run use the latest
            canonical_course_run = published_course_runs[0]
        else:
            # otherwise just use the latest in general
            canonical_course_run = course_runs.first()

        course.canonical_course_run = canonical_course_run
        course.save()


def delete_canonical(apps, schema_editor):
    """Delete the canonical course run associations."""
    Course = apps.get_model('course_metadata', 'Course')
    Course.objects.all().update(canonical_course_run=None)


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0036_course_canonical_course_run'),
    ]

    operations = [
        migrations.RunPython(create_canonical, reverse_code=delete_canonical),
    ]
