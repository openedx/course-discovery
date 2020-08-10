from django.db import migrations, models

EMPTY_NAME = 'Empty'
EMPTY_SLUG = 'empty'

def add_empty_course_type(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')

    CourseType.objects.update_or_create(slug=EMPTY_SLUG, defaults={'name': EMPTY_NAME})
    CourseRunType.objects.update_or_create(slug=EMPTY_SLUG, defaults={'name': EMPTY_NAME, 'is_marketable': False})

def drop_empty_course_type(apps, schema_editor):
    CourseType = apps.get_model('course_metadata', 'CourseType')
    CourseRunType = apps.get_model('course_metadata', 'CourseRunType')

    CourseType.objects.filter(slug__in=EMPTY_SLUG).delete()
    CourseRunType.objects.filter(slug__in=EMPTY_SLUG).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0215_coursetype_white_listed_orgs'),
    ]

    operations = [
        migrations.RunPython(
            code=add_empty_course_type,
            reverse_code=drop_empty_course_type,
        ),
    ]
