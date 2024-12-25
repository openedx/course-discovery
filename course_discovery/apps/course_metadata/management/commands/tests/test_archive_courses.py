from datetime import timedelta
from itertools import product
from unittest import mock

import ddt
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ExternalProductStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import (
    AdditionalMetadataFactory, ArchiveCoursesConfigFactory, CourseFactory, CourseRunFactory
)
from course_discovery.apps.course_metadata.utils import ensure_draft_world


@ddt.ddt
class ArchiveCoursesCommandTests(TestCase):
    """
    Test suite for archive_courses management command.
    """
    def setUp(self):
        super().setUp()

        end = timezone.now() + timedelta(days=5)
        self.course1 = CourseFactory(additional_metadata=AdditionalMetadataFactory(end_date=end))
        self.course2 = CourseFactory(additional_metadata=AdditionalMetadataFactory(end_date=end))
        self.courserun1 = CourseRunFactory(course=self.course1, end=end)
        self.courserun2 = CourseRunFactory(course=self.course2, end=end)

        ensure_draft_world(Course.objects.get(pk=self.course1.pk))
        ensure_draft_world(Course.objects.get(pk=self.course2.pk))

        self.csv_file_content = f"Uuids\n{self.course1.uuid}"
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        ArchiveCoursesConfigFactory.create(csv_file=self.csv_file, enabled=True)

    @ddt.data(
        *list(product([0, 1], repeat=3))
    )
    @ddt.unpack
    def test(self, from_db, mangle_title, mangle_end_date):
        # Some sanity checks on counts
        for model in [Course, CourseRun]:
            assert model.objects.count() == 1
            assert model.everything.count() == 2

        args = self.prepare_cmd_args(from_db, mangle_title, mangle_end_date)
        with mock.patch('course_discovery.apps.api.utils.StudioAPI._update_end_date_in_studio') as mock_studio_call:
            call_command('archive_courses', *args)

        self.course1.refresh_from_db()
        self.course2.refresh_from_db()
        self.verify_archived(self.course1, mangle_title, mangle_end_date)
        self.verify_not_archived(self.course2)

        if mangle_end_date:
            assert mock_studio_call.call_count == 1
        else:
            assert mock_studio_call.call_count == 0

    def prepare_cmd_args(self, from_db, mangle_title, mangle_end_date):
        args = []
        args.extend(['--from-db'] if from_db else ['--type', f'{self.course1.type.slug}'])
        if mangle_title:
            args.append('--mangle-title')
        if mangle_end_date:
            args.append('--mangle-end-date')
        return args

    def verify_archived(self, course, mangle_title, mangle_end_date):
        for c in [course, course.draft_version]:
            assert c.additional_metadata.product_status == ExternalProductStatus.Archived
            assert c.additional_metadata.end_date < timezone.now() + timedelta(minutes=1)
            assert c.course_runs.last().status == CourseRunStatus.Unpublished

            is_title_mangled = c.title.startswith('DELETED')
            assert is_title_mangled if mangle_title else not is_title_mangled

            is_end_date_mangled = c.course_runs.first().end < timezone.now() + timedelta(minutes=1)
            assert is_end_date_mangled if mangle_end_date else not is_end_date_mangled

    def verify_not_archived(self, course):
        for c in [course, course.draft_version]:
            assert c.additional_metadata.product_status == ExternalProductStatus.Published
            assert c.additional_metadata.end_date > timezone.now() + timedelta(minutes=1)
            assert c.course_runs.last().status == CourseRunStatus.Published

            assert not c.title.startswith('DELETED')
            assert not c.course_runs.first().end < timezone.now() + timedelta(minutes=1)
