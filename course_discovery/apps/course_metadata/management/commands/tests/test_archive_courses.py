from datetime import timedelta
from itertools import product
from unittest import mock
from urllib.parse import urljoin

import ddt
import pytest
import responses
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ExternalProductStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import (
    AdditionalMetadataFactory, ArchiveCoursesConfigFactory, CourseFactory, CourseRunFactory
)
from course_discovery.apps.course_metadata.utils import ensure_draft_world


@ddt.ddt
class ArchiveCoursesCommandTests(TestCase, OAuth2Mixin):
    """
    Test suite for archive_courses management command.
    """
    def setUp(self):
        super().setUp()
        self.mock_access_token()

        end = timezone.now() + timedelta(days=5)
        self.course1 = CourseFactory(additional_metadata=AdditionalMetadataFactory(end_date=end))
        self.course2 = CourseFactory(additional_metadata=AdditionalMetadataFactory(end_date=end))
        self.courserun1 = CourseRunFactory(course=self.course1, end=end)
        self.courserun2 = CourseRunFactory(course=self.course2, end=end)
        self.courserun1_studio_url = urljoin(self.course1.partner.studio_url, f"api/v1/course_runs/{self.courserun1.key}/")
        self.courserun2_studio_url = urljoin(self.course2.partner.studio_url, f"api/v1/course_runs/{self.courserun2.key}/")

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
    @responses.activate
    def test(self, from_db, mangle_title, mangle_end_date):
        # Some sanity checks on counts
        for model in [Course, CourseRun]:
            assert model.objects.count() == 2
            assert model.everything.count() == 4

        responses.add(responses.PATCH, self.courserun1_studio_url, status=200)
        responses.add(responses.PATCH, self.courserun2_studio_url, status=200)

        args = self.prepare_cmd_args(from_db, mangle_title, mangle_end_date)
        call_command('archive_courses', *args)

        self.course1.refresh_from_db()
        self.course2.refresh_from_db()
        self.verify_archived(self.course1, mangle_title, mangle_end_date)
        self.verify_not_archived(self.course2)

        if mangle_end_date:
            assert responses.assert_call_count(self.courserun1_studio_url, 1) is True
        else:
            assert responses.assert_call_count(self.courserun1_studio_url, 0) is True

    @ddt.data(
        True,
        False
    )
    @responses.activate
    def test_some_failures(self, is_course1_archived):
        "Test for the case when some courses are archived successfully and some are not"
        responses.add(responses.PATCH, self.courserun1_studio_url, status=200 if is_course1_archived else 500)
        responses.add(responses.PATCH, self.courserun2_studio_url, status=500 if is_course1_archived else 200)
        self.csv_file_content = f"Uuids\n{self.course1.uuid}\n{self.course2.uuid}"
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        ArchiveCoursesConfigFactory.create(csv_file=self.csv_file, enabled=True)

        args = self.prepare_cmd_args(True, True, True)
        call_command('archive_courses', *args)

        self.course1.refresh_from_db()
        self.course2.refresh_from_db()
        archived_course = self.course1 if is_course1_archived else self.course2
        not_archived_course = self.course2 if is_course1_archived else self.course1
        self.verify_archived(archived_course, True, True)
        self.verify_not_archived(not_archived_course)

    def test_raises_error_if_not_enough_arguments(self):
        with pytest.raises(CommandError):
            call_command("archive_courses")

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
