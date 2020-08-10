from django.db import migrations, models


def clear_slug_values(apps, schema_editor):
    """
    Clears all data in the CourseRun.slug column.

    The data is invalid, and needs to be removed so that it can be refreshed.
    """
    CourseRun = apps.get_model('course_metadata', 'CourseRun')
    CourseRun.objects.all().update(slug=None)


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0022_remove_duplicate_courses'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='slug',
            field=models.CharField(max_length=255, db_index=True, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='slug',
            field=models.CharField(max_length=255, db_index=True, blank=True, null=True),
        ),
        migrations.RunPython(clear_slug_values, reverse_code=migrations.RunPython.noop),
    ]
