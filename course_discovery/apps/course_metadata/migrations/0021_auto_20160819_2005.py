import uuid

import django.db.models.deletion
import django_extensions.db.fields
import sortedm2m.fields
from django.db import migrations, models


def delete_partnerless_courses(apps, schema_editor):
    Course = apps.get_model('course_metadata', 'Course')
    Course.objects.filter(partner__isnull=True).delete()


def add_uuid_to_courses_and_course_runs(apps, schema_editor):
    Course = apps.get_model('course_metadata', 'Course')
    CourseRun = apps.get_model('course_metadata', 'CourseRun')

    for objects in (Course.objects.filter(uuid__isnull=True), CourseRun.objects.filter(uuid__isnull=True)):
        for obj in objects:
            obj.uuid = uuid.uuid4()
            obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0020_auto_20160819_1942'),
    ]

    operations = [
        migrations.RunPython(delete_partnerless_courses, reverse_code=migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='courseorganization',
            unique_together=set(),
        ),
        migrations.AlterIndexTogether(
            name='courseorganization',
            index_together=set(),
        ),
        migrations.RemoveField(
            model_name='courseorganization',
            name='course',
        ),
        migrations.RemoveField(
            model_name='courseorganization',
            name='organization',
        ),
        migrations.AlterModelOptions(
            name='course',
            options={},
        ),
        migrations.RemoveField(
            model_name='courserun',
            name='image',
        ),
        migrations.RemoveField(
            model_name='courserun',
            name='instructors',
        ),
        migrations.RemoveField(
            model_name='courserun',
            name='marketing_url',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='image',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='learner_testimonial',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='marketing_url',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='image',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='marketing_url',
        ),
        migrations.AddField(
            model_name='course',
            name='authoring_organizations',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.Organization',
                                                         related_name='authored_courses'),
        ),
        migrations.AddField(
            model_name='course',
            name='card_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, populate_from='key', editable=False),
        ),
        migrations.AddField(
            model_name='course',
            name='sponsoring_organizations',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.Organization',
                                                         related_name='sponsored_courses'),
        ),
        migrations.AddField(
            model_name='course',
            name='uuid',
            field=models.UUIDField(editable=False, verbose_name='UUID', null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='card_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, populate_from='key', editable=False),
        ),
        migrations.AddField(
            model_name='courserun',
            name='uuid',
            field=models.UUIDField(editable=False, verbose_name='UUID', null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='card_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, populate_from='key', editable=False),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='uuid',
            field=models.UUIDField(editable=False, verbose_name='UUID', null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='card_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, populate_from='key', editable=False),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='uuid',
            field=models.UUIDField(editable=False, verbose_name='UUID', null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='key',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='course',
            name='partner',
            field=models.ForeignKey(to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='key',
            field=models.CharField(max_length=255),
        ),
        migrations.RunPython(add_uuid_to_courses_and_course_runs, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='course',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AlterUniqueTogether(
            name='course',
            unique_together={('partner', 'key'), ('partner', 'uuid')},
        ),
        migrations.RemoveField(
            model_name='course',
            name='image',
        ),
        migrations.RemoveField(
            model_name='course',
            name='learner_testimonial',
        ),
        migrations.RemoveField(
            model_name='course',
            name='marketing_url',
        ),
        migrations.RemoveField(
            model_name='course',
            name='organizations',
        ),
        migrations.DeleteModel(
            name='CourseOrganization',
        ),

    ]
