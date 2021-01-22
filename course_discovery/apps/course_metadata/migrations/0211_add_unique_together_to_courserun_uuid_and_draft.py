# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-10-29 12:41
from __future__ import unicode_literals

import uuid

from django.db import migrations
from django.db.models import Count

class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0210_no_additional_info_validation'),
    ]

    def migrate_data_forward(apps, schema_editor):
        """
        Data needs to be migrated forward for this migration to occur, in that we previously did not  require
        any uniqueness on our Course Run UUIDs due to microsite support (though because of key uniqueness, if you had
        an identical course run between two, you still were not able to save that course run). This created a new
        UUID for a run where a key was modified to successfully save, but the UUID was not, and updates relevant drafts.
        """
        CourseRun = apps.get_model('course_metadata', 'CourseRun')

        duplicate_uuid_values = CourseRun.everything.values_list('uuid', flat=True).annotate(Count('uuid')).filter(
            uuid__count__gt=1,
            draft=False,  # Only official rows should ever need this migration
        )

        for duplicate_uuid_value in duplicate_uuid_values:
            duplicate_course_runs = CourseRun.everything.filter(uuid=duplicate_uuid_value, draft=False).order_by(
                'created')
            if duplicate_course_runs.count() > 1:
                # Skip the first element as we don't need to update it
                for duplicate_course_run in duplicate_course_runs[1:]:
                    new_uuid = uuid.uuid4()
                    duplicate_course_run.uuid = new_uuid
                    duplicate_course_run.save()
                    if duplicate_course_run.draft_version:
                        duplicate_course_run.draft_version.uuid = new_uuid
                        duplicate_course_run.draft_version.save()

    operations = [
        migrations.RunPython(
            migrate_data_forward,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.AlterUniqueTogether(
            name='courserun',
            unique_together=set([('uuid', 'draft'), ('key', 'draft')]),
        ),

    ]
