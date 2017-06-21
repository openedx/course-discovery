import ddt
import mock
from django.core.management import CommandError, call_command
from django.db import IntegrityError
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import (CourseFactory, CourseRunFactory, OrganizationFactory,
                                                                   PersonFactory, SeatFactory, SubjectFactory)
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.dataloader.create_courses import logger as dataloader_logger
from course_discovery.apps.publisher.dataloader.update_course_runs import logger as update_logger
from course_discovery.apps.publisher.models import Course as Publisher_Course
from course_discovery.apps.publisher.models import CourseRun as Publisher_CourseRun
from course_discovery.apps.publisher.tests import factories


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

    @mock.patch('course_discovery.apps.publisher.dataloader.create_courses.process_course')
    def test_query_return_correct_course(self, process_course):
        """ Verify that query return correct courses using start and end ids. """
        call_command(self.command_name, *self.command_args)
        call_list = [mock.call(self.course), ]
        self.assertEqual(call_list, process_course.call_args_list)

    @mock.patch('course_discovery.apps.publisher.dataloader.create_courses.process_course')
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


# pylint: disable=no-member
@ddt.ddt
class CreateCoursesTests(TestCase):
    def setUp(self):
        super(CreateCoursesTests, self).setUp()

        transcript_languages = LanguageTag.objects.all()[:2]
        self.subjects = SubjectFactory.create_batch(3)
        self.course = CourseFactory(subjects=self.subjects)

        self.command_name = 'import_metadata_courses'
        self.command_args = ['--start_id={}'.format(self.course.id), '--end_id={}'.format(self.course.id)]

        # create multiple course-runs against course.
        course_runs = CourseRunFactory.create_batch(
            3, course=self.course, transcript_languages=transcript_languages,
            language=transcript_languages[0],
            short_description_override='Testing description'
        )

        canonical_course_run = course_runs[0]
        for seat_type in ['honor', 'credit', 'verified']:  # to avoid same type seat creation.
            SeatFactory(course_run=canonical_course_run, type=seat_type)

        staff = PersonFactory.create_batch(2)
        canonical_course_run.staff.add(*staff)

        self.course.canonical_course_run = canonical_course_run
        self.course.save()

        # create org and assign to the course-metadata
        self.forganization_extension = factories.OrganizationExtensionFactory()
        self.organization = self.forganization_extension.organization
        self.course.authoring_organizations.add(self.organization)

    def test_course_create_successfully(self):
        """ Verify that publisher course successfully."""
        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()

        self._assert_course(course)
        self._assert_course_run(course.course_runs.first(), self.course.canonical_course_run)
        self._assert_seats(course.course_runs.first(), self.course.canonical_course_run)

    def test_course_create_without_video(self):
        """ Verify that publisher course successfully."""
        self.course.video = None
        self.course.save()

        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()

        self._assert_course(course)
        self._assert_course_run(course.course_runs.first(), self.course.canonical_course_run)
        self._assert_seats(course.course_runs.first(), self.course.canonical_course_run)

    def test_course_having_multiple_auth_organizations(self):
        """ Verify that if the course has multiple organization then that course will be
        imported to publisher but with only 1 organization.
        """
        # later that record will be updated with dual org manually.

        org2 = OrganizationFactory()
        self.course.authoring_organizations.add(org2)

        call_command(self.command_name, *self.command_args)
        course = Publisher_Course.objects.all().first()

        self._assert_course(course)

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

    def _assert_course(self, publisher_course):
        """ Verify that publisher course  and metadata course has correct values."""

        # assert organization
        self.assertEqual(publisher_course.organizations.first(), self.organization)

        self.assertEqual(publisher_course.title, self.course.title)
        self.assertEqual(publisher_course.number, self.course.number)
        self.assertEqual(publisher_course.short_description, self.course.short_description)
        self.assertEqual(publisher_course.full_description, self.course.full_description)
        self.assertEqual(publisher_course.level_type, self.course.level_type)

        # each course will have only 1 course-run
        self.assertEqual(publisher_course.course_runs.all().count(), 1)
        self.assertEqual(publisher_course.course_metadata_pk, self.course.pk)
        self.assertEqual(publisher_course.primary_subject, self.subjects[0])
        self.assertEqual(publisher_course.secondary_subject, self.subjects[1])
        self.assertEqual(publisher_course.tertiary_subject, self.subjects[2])

        if self.course.video:
            self.assertEqual(publisher_course.video_link, self.course.video.src)
        else:
            self.assertFalse(publisher_course.video_link)

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
        self.assertEqual(
            publisher_course_run.short_description_override, metadata_course_run.short_description_override
        )

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


# pylint: disable=no-member
@ddt.ddt
class UpdateCourseRunsTests(TestCase):
    def setUp(self):
        super(UpdateCourseRunsTests, self).setUp()

        self.update_command_name = 'update_publisher_course_runs'
        # create multiple course-runs against course.

        self.metadata_course_runs = []
        self.publisher_runs = []
        # add metadata course-runs and add publisher course runs
        for i in range(1, 3):
            course_run = CourseRunFactory(
                short_description_override='short description {}'.format(i),
                full_description_override='full description {}'.format(i),
                title_override='title {}'.format(i)
            )

            self.metadata_course_runs.append(course_run)
            self.publisher_runs.append(factories.CourseRunFactory(lms_course_id=course_run.key))

        self.command_args = [
            '--start_id={}'.format(self.publisher_runs[0].id), '--end_id={}'.format(self.publisher_runs[-1].id)
        ]

    def test_course_run_update_successfully(self):
        """ Verify that publisher course run updates successfully."""
        self.assert_publisher_course_runs_before_update()
        call_command(self.update_command_name, *self.command_args)
        self.assert_updated_course_runs()

    def test_course_run_does_not_update_if_values_empty(self):
        """ Verify that publisher course run not updates."""
        self.assert_publisher_course_runs_before_update()

        for run in self.metadata_course_runs:
            course_run = CourseRun.objects.filter(key=run.key).first()
            course_run.short_description_override = None
            course_run.title_override = None
            course_run.full_description_override = None
            course_run.save()
        call_command(self.update_command_name, *self.command_args)

        # values remains unchanged.
        self.assert_publisher_course_runs_before_update()

    def test_successfully_log_message(self):
        """ Verify that script logs the successful message after import."""
        command_args = [
            '--start_id={}'.format(self.publisher_runs[0].id), '--end_id={}'.format(self.publisher_runs[0].id)
        ]
        with LogCapture(update_logger.name) as log_capture:
            call_command(self.update_command_name, *command_args)
            log_capture.check(
                (
                    update_logger.name,
                    'INFO',
                    'Update course-run import with id [{}], lms_course_id [{}].'.format(
                        self.publisher_runs[0].id, self.publisher_runs[0].lms_course_id
                    )
                )
            )

    def test_script_logs_error_message(self):
        """ Verify that script logs the error message if any error occur."""
        command_args = [
            '--start_id={}'.format(self.publisher_runs[0].id), '--end_id={}'.format(self.publisher_runs[0].id)
        ]

        with mock.patch.object(Publisher_CourseRun, "save") as mock_method:
            mock_method.side_effect = IntegrityError
            with LogCapture(update_logger.name) as log_capture:
                call_command(self.update_command_name, *command_args)
                log_capture.check(
                    (
                        update_logger.name,
                        'ERROR',
                        'Exception appear in updating course-run-id [{}].'.format(
                            self.publisher_runs[0].id
                        )
                    )
                )

    def assert_publisher_course_runs_before_update(self):
        """ Assert method to verify the course runs before updation."""
        for course_run in self.metadata_course_runs:
            publisher_course_run = Publisher_CourseRun.objects.filter(lms_course_id=course_run.key).first()
            self.assertNotEqual(publisher_course_run.short_description_override, course_run.short_description_override)
            self.assertNotEqual(publisher_course_run.title_override, course_run.title_override)
            self.assertNotEqual(publisher_course_run.full_description_override, course_run.full_description_override)

    def assert_updated_course_runs(self):
        """ Assert method to verify the course runs after updation."""
        for course_run in self.metadata_course_runs:
            publisher_course_run = Publisher_CourseRun.objects.filter(lms_course_id=course_run.key).first()

            self.assertEqual(
                publisher_course_run.short_description_override, course_run.short_description_override
            )
            self.assertEqual(
                publisher_course_run.title_override, course_run.title_override
            )
            self.assertEqual(
                publisher_course_run.full_description_override, course_run.full_description_override
            )
