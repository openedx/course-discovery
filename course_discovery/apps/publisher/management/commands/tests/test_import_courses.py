import ddt
import mock
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.test import TestCase
from guardian.shortcuts import get_group_perms
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.tests.factories import (CourseFactory, CourseRunFactory, OrganizationFactory,
                                                                   PersonFactory, SeatFactory, SubjectFactory)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import REVIEWER_GROUP_NAME
from course_discovery.apps.publisher.dataloader.create_courses import logger as dataloader_logger
from course_discovery.apps.publisher.models import Course as Publisher_Course
from course_discovery.apps.publisher.models import CourseRun as Publisher_CourseRun
from course_discovery.apps.publisher.models import OrganizationExtension
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import GroupFactory


@ddt.ddt
class ImportCoursesCommandTests(TestCase):
    def setUp(self):
        super(ImportCoursesCommandTests, self).setUp()
        self.command_name = 'import_metadata_courses'

    @ddt.data(
        [''],  # Raises error because both args are missing
        ['--start_id=1'],  # Raises error because 'start_id' is not provided
        ['--end_id=2'],  # Raises error because 'end_id' is not provided
    )
    def test_missing_required_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments are missing """

        # If a required argument is not specified the system should raise a CommandError
        with self.assertRaises(CommandError):
            call_command(self.command_name, *command_args)

    @ddt.data(
        ['--start_id=1', '--end_id=x'],  # Raises error because 'end_id has invalid value
        ['--start_id=x', '--end_id=1']  # Raises error because both args has invalid value
    )
    def test_with_invalid_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments has invalid values """

        with self.assertRaises(ValueError):
            call_command(self.command_name, *command_args)


# pylint: disable=no-member
@ddt.ddt
class ImportCoursesTests(TestCase):
    def setUp(self):
        super(ImportCoursesTests, self).setUp()
        self.course = CourseFactory()
        self.course_runs = CourseRunFactory.create_batch(3, course=self.course)
        self.course.canonical_course_run = self.course_runs[2]
        self.course.save()

        # add multiple courses.
        self.course_2 = CourseFactory()

        self.command_name = 'import_metadata_courses'
        self.command_args = ['--start_id={}'.format(self.course.id), '--end_id={}'.format(self.course.id)]

    @mock.patch('course_discovery.apps.publisher.management.commands.import_metadata_courses.process_course')
    def test_query_return_correct_course(self, process_course):
        """ Verify that query return correct courses using start and end ids. """
        call_command(self.command_name, *self.command_args)
        call_list = [mock.call(self.course), ]
        self.assertEqual(call_list, process_course.call_args_list)

    @mock.patch('course_discovery.apps.publisher.management.commands.import_metadata_courses.process_course')
    def test_query_return_correct_courses(self, process_course):
        """ Verify that query return correct courses using start and end ids. """
        course_3 = CourseFactory()
        call_command(self.command_name, *['--start_id={}'.format(self.course_2.id), '--end_id={}'.format(course_3.id)])
        call_list = [mock.call(self.course_2), mock.call(course_3), ]
        self.assertEqual(call_list, process_course.call_args_list)

    @mock.patch('course_discovery.apps.publisher.dataloader.create_courses.create_or_update_course')
    def test_course_without_auth_organization(self, create_or_update_course):
        """ Verify that if the course has no organization then that course will not be
        imported to publisher.
        """
        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    dataloader_logger.name,
                    'WARNING',
                    'Course has no organization. Course uuid is [{}].'.format(self.course.uuid)
                )
            )
            create_or_update_course.assert_not_called()

    @mock.patch('course_discovery.apps.publisher.dataloader.create_courses.create_or_update_course')
    def test_course_having_multiple_auth_organizations(self, create_or_update_course):
        """ Verify that if the course has multiple organization then that course will not be
        imported to publisher.
        """
        self.course.authoring_organizations.add(OrganizationFactory())
        self.course.authoring_organizations.add(OrganizationFactory())

        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    dataloader_logger.name,
                    'WARNING',
                    'Course has more than 1 organization. Course uuid is [{}].'.format(self.course.uuid)
                )
            )
            create_or_update_course.assert_not_called()


# pylint: disable=no-member
@ddt.ddt
class CreateCoursesTests(TestCase):
    def setUp(self):
        super(CreateCoursesTests, self).setUp()

        transcript_languages = LanguageTag.objects.all()[:2]
        self.course = CourseFactory()

        self.command_name = 'import_metadata_courses'
        self.command_args = ['--start_id={}'.format(self.course.id), '--end_id={}'.format(self.course.id)]

        # create multiple course-runs against course.
        course_runs = CourseRunFactory.create_batch(
            3, course=self.course, transcript_languages=transcript_languages,
            language=transcript_languages[0]
        )

        canonical_course_run = course_runs[0]
        for seat_type in ['honor', 'credit', 'verified']:  # to avoid same type seat creation.
            SeatFactory(course_run=canonical_course_run, type=seat_type)

        staff = PersonFactory.create_batch(2)
        canonical_course_run.staff.add(*staff)

        self.course.canonical_course_run = canonical_course_run
        self.course.save()

        # create org and assign to the course-metadata
        self.organization = OrganizationFactory()
        self.course.authoring_organizations.add(self.organization)

    def test_course_create_successfully(self):
        """ Verify that publisher course without default user roles and subjects."""

        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()

        self._assert_course(course)
        self._assert_course_run(course.course_runs.first(), self.course.canonical_course_run)
        self._assert_seats(course.course_runs.first(), self.course.canonical_course_run)
        self.assertFalse(course.course_user_roles.all())
        self.assertFalse(self.course.subjects.all())

    def test_course_create_successfully_with_roles(self):
        """ Verify that publisher course with default roles and subjects."""
        for role, __ in PublisherUserRole.choices:
            factories.OrganizationUserRoleFactory(role=role, organization=self.organization)

        subjects = SubjectFactory.create_batch(3)
        self.course.subjects.add(*subjects)

        call_command(self.command_name, *self.command_args)
        publisher_course = Publisher_Course.objects.all().first()

        self._assert_course(publisher_course)
        self._assert_course_run(publisher_course.course_runs.first(), self.course.canonical_course_run)
        self._assert_seats(publisher_course.course_runs.first(), self.course.canonical_course_run)

        roles = publisher_course.course_user_roles.all()
        for role in PublisherUserRole.choices:
            self.assertEqual(roles.get(role=role[0]).role, role[0])

        subjects = self.course.subjects.all()
        self.assertEqual(subjects[0], publisher_course.primary_subject)
        self.assertEqual(subjects[1], publisher_course.secondary_subject)
        self.assertEqual(subjects[2], publisher_course.tertiary_subject)

    def test_course_does_not_create_twice(self):
        """ Verify that course does not create two course with same title and number.
            Just update.
        """
        call_command(self.command_name, *self.command_args)
        self.assertEqual(Publisher_Course.objects.all().count(), 1)
        course = Publisher_Course.objects.all().first()
        self._assert_course(course)

        self.assertEqual(Publisher_CourseRun.objects.all().count(), 1)
        self._assert_course_run(course.course_runs.first(), self.course.canonical_course_run)

        # try to import the course with same ids.
        call_command(self.command_name, *self.command_args)
        self.assertEqual(Publisher_Course.objects.all().count(), 1)
        course = Publisher_Course.objects.all().first()
        self._assert_course(course)
        self.assertEqual(Publisher_CourseRun.objects.all().count(), 1)
        self._assert_course_run(course.course_runs.first(), self.course.canonical_course_run)

    def test_course_without_canonical_course_run(self):
        """ Verify that import works fine even if course has no canonical-course-run."""
        self.course.canonical_course_run = None
        self.course.save()

        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            publisher_course = Publisher_Course.objects.all().first()
            log_capture.check(
                (
                    dataloader_logger.name,
                    'INFO',
                    'Import course with id [{}], number [{}].'.format(publisher_course.id, publisher_course.number)
                ),
                (
                    dataloader_logger.name,
                    'WARNING',
                    'Canonical course-run not found for metadata course [{}].'.format(self.course.uuid)
                ),
            )

    def test_course_run_without_seats(self):
        """ Verify that import works fine even if course-run has no seats."""
        self.course.canonical_course_run.seats.all().delete()

        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            publisher_course = Publisher_Course.objects.all().first()
            publisher_run = publisher_course.course_runs.first()
            log_capture.check(
                (
                    dataloader_logger.name,
                    'INFO',
                    'Import course with id [{}], number [{}].'.format(publisher_course.id, publisher_course.number)
                ),
                (
                    dataloader_logger.name,
                    'INFO',
                    'Import course-run with id [{}], lms_course_id [{}].'.format(
                        publisher_run.id, publisher_run.lms_course_id
                    )
                ),
                (
                    dataloader_logger.name,
                    'WARNING',
                    'No seats found for course-run [{}].'.format(
                        self.course.canonical_course_run.uuid
                    )
                ),
            )

    def test_course_create_with_org_extension(self):
        """ Verify that publisher course having organization-ext."""
        factories.OrganizationExtensionFactory(
            organization=self.course.authoring_organizations.all().first()
        )
        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()
        self._assert_course(course)

    def test_course_create_with_empty_org_key(self):
        """ Verify that publisher course having organization-ext."""
        org = self.course.authoring_organizations.all().first()
        org.key = ''
        org.save()
        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    dataloader_logger.name,
                    'WARNING',
                    'Organization key has empty value [{}].'.format(org.uuid)
                ),
            )

    def test_organization_ext_with_duplicate_organization(self):
        """ Verify that if organization-ext already exists but with different group it will raise error
        if it comes again with different org."""

        # make org and create its org-ext object.
        organization = OrganizationFactory(name='test-org', key='testing')
        factories.OrganizationExtensionFactory(
            organization=organization, group=GroupFactory(name='testing name')
        )

        # update org key to a same group name so that it will raise exception.
        course_organization = self.course.authoring_organizations.all().first()
        course_organization.key = 'testing name'
        course_organization.save()

        with LogCapture(dataloader_logger.name) as log_capture:
            call_command(self.command_name, *self.command_args)
            log_capture.check(
                (
                    dataloader_logger.name,
                    'ERROR',
                    'Exception appear for course-id [{}].'.format(self.course.uuid)
                ),
            )

    def _assert_course(self, publisher_course):
        """ Verify that publisher course  and metadata course has correct values."""

        self.assertEqual(publisher_course.title, self.course.title)
        self.assertEqual(publisher_course.number, self.course.number)
        self.assertEqual(publisher_course.short_description, self.course.short_description)
        self.assertEqual(publisher_course.full_description, self.course.full_description)
        self.assertEqual(publisher_course.level_type, self.course.level_type)

        # each course will have only 1 course-run
        self.assertEqual(publisher_course.course_runs.all().count(), 1)
        self.assertEqual(publisher_course.course_metadata_pk, self.course.pk)

    def _assert_course_run(self, publisher_course_run, metadata_course_run):
        """ Verify that publisher course-run and metadata course run has correct values."""

        self.assertEqual(publisher_course_run.start, metadata_course_run.start)
        self.assertEqual(publisher_course_run.end, metadata_course_run.end)
        self.assertEqual(
            publisher_course_run.enrollment_start, metadata_course_run.enrollment_start
        )
        self.assertEqual(
            publisher_course_run.enrollment_end, metadata_course_run.enrollment_end
        )

        self.assertEqual(publisher_course_run.min_effort, metadata_course_run.min_effort)
        self.assertEqual(publisher_course_run.max_effort, metadata_course_run.max_effort)
        self.assertEqual(publisher_course_run.length, metadata_course_run.weeks_to_complete)
        self.assertEqual(publisher_course_run.language, metadata_course_run.language)
        self.assertEqual(publisher_course_run.pacing_type, metadata_course_run.pacing_type)
        self.assertEqual(publisher_course_run.card_image_url, metadata_course_run.card_image_url)
        self.assertEqual(publisher_course_run.language, metadata_course_run.language)
        self.assertEqual(publisher_course_run.lms_course_id, metadata_course_run.key)

        # assert ManytoMany fields.
        self.assertEqual(
            list(publisher_course_run.transcript_languages.all()), list(metadata_course_run.transcript_languages.all())
        )
        self.assertEqual(list(publisher_course_run.staff.all()), list(metadata_course_run.staff.all()))

    def _assert_seats(self, publisher_course_run, metadata_course_run):
        """ Verify that canonical course-run seats imported into publisher app with valid data."""
        metadata_seats = metadata_course_run.seats.all()
        publisher_seats = publisher_course_run.seats.all()
        self.assertEqual(metadata_seats.count(), publisher_seats.count())
        self.assertListEqual(
            sorted([(seat.type, seat.price, seat.credit_provider, seat.currency) for seat in metadata_seats]),
            sorted([(seat.type, seat.price, seat.credit_provider, seat.currency) for seat in publisher_seats])
        )

    def test_organization_extension_permission(self):
        """
        Verify that required permissions assigned to OrganizationExtension object.
        """
        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()
        organization_extension = course.organizations.first().organization_extension

        course_team_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN,
            OrganizationExtension.EDIT_COURSE_RUN
        ]

        self._assert_permissions(
            organization_extension, organization_extension.group, course_team_permissions
        )

        marketing_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self._assert_permissions(
            organization_extension, Group.objects.get(name=REVIEWER_GROUP_NAME), marketing_permissions
        )

    def _assert_permissions(self, organization_extension, group, expected_permissions):
        permissions = get_group_perms(group, organization_extension)
        self.assertEqual(sorted(permissions), sorted(expected_permissions))
