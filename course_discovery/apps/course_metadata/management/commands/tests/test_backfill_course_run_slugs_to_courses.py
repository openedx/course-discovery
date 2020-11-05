from unittest import mock

import ddt
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.models import BackfillCourseRunSlugsConfig, CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory


@ddt.ddt
class BackfillCourseRunSlugsToCoursesCommandTests(TestCase):
    LOGGER = 'course_discovery.apps.course_metadata.management.commands.backfill_course_run_slugs_to_courses.logger'

    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(marketing_site_api_password=None)
        self.course1 = CourseFactory(partner=self.partner, draft=False)
        self.course2 = CourseFactory(partner=self.partner, draft=False)
        self.course1UnpublishedRun = CourseRunFactory(course=self.course1, status=CourseRunStatus.Unpublished)
        self.course1PublishedRun = CourseRunFactory(course=self.course1, status=CourseRunStatus.Published)
        self.course2PublishedRun = CourseRunFactory(course=self.course2, status=CourseRunStatus.Published)

    def test_missing_arguments(self):
        with self.assertRaises(CommandError):
            call_command('backfill_course_run_slugs_to_courses')

    def test_conflicting_arguments(self):
        with self.assertRaises(CommandError):
            call_command('backfill_course_run_slugs_to_courses', '--args-from-database', '--all')
        with self.assertRaises(CommandError):
            call_command('backfill_course_run_slugs_to_courses', '--all', '-uuids', self.course1.uuid)
        with self.assertRaises(CommandError):
            call_command('backfill_course_run_slugs_to_courses', '-uuids', self.course1.uuid, '--args-from-database')

    @ddt.data(
        ('command_line', '--all'),
        ('database', '--args-from-database'),
    )
    @ddt.unpack
    def test_backfill_all(self, argument_source, argument):
        course1_active_url_slug = self.course1.active_url_slug
        course2_active_url_slug = self.course2.active_url_slug

        if argument_source == 'database':
            config = BackfillCourseRunSlugsConfig.get_solo()
            config.all = True
            config.save()
        call_command('backfill_course_run_slugs_to_courses', argument)

        course1_url_slugs = [slug_obj.url_slug for slug_obj in self.course1.url_slug_history.all()]
        course2_url_slugs = [slug_obj.url_slug for slug_obj in self.course2.url_slug_history.all()]

        # make sure active url_slugs remain unchanged
        self.assertEqual(self.course1.active_url_slug, course1_active_url_slug)
        self.assertIn(self.course1PublishedRun.slug, course1_url_slugs)
        self.assertNotIn(self.course1UnpublishedRun.slug, course1_url_slugs)
        self.assertEqual(self.course2.active_url_slug, course2_active_url_slug)
        self.assertIn(self.course2PublishedRun.slug, course2_url_slugs)

    @ddt.data('command_line', 'database',)
    def test_backfill_specific_course(self, argument_source):
        course1_active_url_slug = self.course1.active_url_slug
        course2_active_url_slug = self.course2.active_url_slug
        if argument_source == 'database':
            config = BackfillCourseRunSlugsConfig.get_solo()
            config.uuids = self.course1.uuid
            config.save()
            call_command('backfill_course_run_slugs_to_courses', '--args-from-database')
        else:
            call_command('backfill_course_run_slugs_to_courses', '-uuids', self.course1.uuid)

        course1_url_slugs = [slug_obj.url_slug for slug_obj in self.course1.url_slug_history.all()]
        self.assertEqual(self.course1.active_url_slug, course1_active_url_slug)
        self.assertIn(self.course1PublishedRun.slug, course1_url_slugs)

        # check we didn't change anything for course2
        self.assertEqual(self.course2.active_url_slug, course2_active_url_slug)
        self.assertEqual(self.course2.url_slug_history.count(), 1)

    def test_specific_uuids_take_priority_in_database_config(self):
        course1_active_url_slug = self.course1.active_url_slug
        course2_active_url_slug = self.course2.active_url_slug

        config = BackfillCourseRunSlugsConfig.get_solo()
        config.uuids = self.course1.uuid
        config.all = True
        config.save()
        call_command('backfill_course_run_slugs_to_courses', '--args-from-database')

        course1_url_slugs = [slug_obj.url_slug for slug_obj in self.course1.url_slug_history.all()]
        self.assertEqual(self.course1.active_url_slug, course1_active_url_slug)
        self.assertIn(self.course1PublishedRun.slug, course1_url_slugs)

        # check we didn't change anything for course2
        self.assertEqual(self.course2.active_url_slug, course2_active_url_slug)
        self.assertEqual(self.course2.url_slug_history.count(), 1)

    @mock.patch(LOGGER)
    def test_unable_to_add_duplicate_slugs(self, mock_logger):
        # add a slug from a course1 run to course2
        self.course2.url_slug_history.create(course=self.course2, partner=self.course2.partner,
                                             url_slug=self.course1PublishedRun.slug)
        # try to backfill course1 slugs
        call_command('backfill_course_run_slugs_to_courses', '-uuids', self.course1.uuid)
        desired_warning = 'Cannot add slug {slug} to course {uuid0}. Slug already belongs to course {uuid1}'.format(
            slug=self.course1PublishedRun.slug,
            uuid0=self.course1.uuid,
            uuid1=self.course2.uuid
        )
        mock_logger.warning.assert_called_with(desired_warning)
