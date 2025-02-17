# Generated by Django 4.2.18 on 2025-02-17 15:50

from django.db import migrations, models
from course_discovery.apps.course_metadata.choices import PathwayStatus


def set_status_on_existing_pathways(apps, schema_editor):
    # For all existing pathways, we set the status to Published.
    # Any deviations from that should be handled manually.
    Pathway = apps.get_model('course_metadata', 'Pathway')
    Pathway.objects.update(status=PathwayStatus.Published)


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0346_archivecoursesconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='pathway',
            name='status',
            field=models.CharField(choices=[('unpublished', 'Unpublished'), ('published', 'Published'), ('retired', 'Retired')], default='unpublished', max_length=255),
        ),
        migrations.RunPython(set_status_on_existing_pathways, migrations.RunPython.noop)
    ]
