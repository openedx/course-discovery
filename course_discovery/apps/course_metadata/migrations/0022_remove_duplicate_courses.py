from django.db import migrations


def remove_duplicate_courses(apps, schema_editor):
    Course = apps.get_model('course_metadata', 'Course')
    duplicates = Course.objects.raw('SELECT'
                                    '   c.* '
                                    'FROM '
                                    '  course_metadata_course AS c'
                                    '  JOIN ('
                                    '    SELECT'
                                    '      LOWER(`key`) AS `key`,'
                                    '      COUNT(1)'
                                    '    FROM'
                                    '      course_metadata_course'
                                    '    GROUP BY'
                                    '      LOWER(`key`)'
                                    '    HAVING'
                                    '      COUNT(1) > 1'
                                    '  ) AS dupes ON dupes.key = LOWER(c.key)')

    for course in duplicates:
        course.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0021_auto_20160819_2005'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_courses, reverse_code=migrations.RunPython.noop),
    ]
