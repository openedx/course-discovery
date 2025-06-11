"""
Unit tests for the send_course_deadline_emails management command.
"""
from datetime import timedelta
from unittest import mock

import ddt
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseFactory, CourseRunFactory, OrganizationFactory, PartnerFactory, SeatFactory,
    SeatTypeFactory, SourceFactory
)
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.tests.factories import OrganizationUserRoleFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.send_course_deadline_emails'


@ddt.ddt
class SendCourseDeadlineEmailsTests(TestCase):
    """
    Test suite for the send_course_deadline_emails management command.
    """
    def setUp(self):
        self.partner = PartnerFactory(id=settings.DEFAULT_PARTNER_ID)
        self.organization = OrganizationFactory()
        self.product_source = SourceFactory(slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG)
        self.draft_course = CourseFactory(
            partner=self.partner,
            product_source=self.product_source,
            draft=True,
            authoring_organizations=[self.organization],
        )
        self.non_draft_course = CourseFactory(
            draft=False, draft_version=self.draft_course, uuid=self.draft_course.uuid,
            authoring_organizations=[self.organization],
            product_source=self.product_source,
        )
        self.draft_course_run = CourseRunFactory(
            course=self.draft_course,
            pacing_type=CourseRunPacing.Self,
            status=CourseRunStatus.Published,
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=5),
            draft=True,
        )
        self.non_draft_course_run = CourseRunFactory(
            course=self.non_draft_course, draft_version=self.draft_course_run, key=self.draft_course_run.key,
            status=CourseRunStatus.Published,
            pacing_type=CourseRunPacing.Self,
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=5),
            draft=False,
        )
        SeatFactory(
            course_run=self.draft_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=timezone.now() + timedelta(days=5)
        )
        SeatFactory(
            course_run=self.non_draft_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=timezone.now() + timedelta(days=5)
        )

        self.user = UserFactory()
        self.course_editor = CourseEditorFactory(
            course=self.non_draft_course,
            user=self.user
        )
        OrganizationUserRoleFactory(
            organization=self.organization,
            user=self.user,
            role=InternalUserRole.ProjectCoordinator
        )

    def run_command(self):
        call_command('send_course_deadline_emails')

    def test_with_no_course_run_with_end_date_within_range(self):
        """
        Test that the command does not send emails when there are no course runs with end dates
        within the specified range.
        """
        with LogCapture(LOGGER_PATH) as log_capture:
            self.run_command()
            log_capture.check(
                (
                    LOGGER_PATH,
                    'INFO',
                    "Initializing course deadline email management command."
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    'Found 0 courses with self-paced runs.'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    "No courses with deadline within the specified range were found."
                ),
            )

    @ddt.data(
        (2, "two_days_reminder"), (7, "seven_days_reminder"), (-1, "course_ended")
    )
    @ddt.unpack
    @mock.patch('course_discovery.apps.course_metadata.tasks.process_send_course_deadline_email.apply_async')
    def test_with_course_run_with_end_date_within_range(
        self, days_until_end, expected_deadline_variant, mock_apply_async
    ):
        """
        Test that the command sends emails when there are advertised course runs with end dates within
        the specified range.
        """
        self.non_draft_course_run.end = timezone.now() + timedelta(days=days_until_end)
        self.non_draft_course_run.save()

        with LogCapture(LOGGER_PATH) as log_capture:
            self.run_command()

        # pylint: disable=line-too-long
            log_capture.check(
                (LOGGER_PATH, 'INFO', "Initializing course deadline email management command."),
                (LOGGER_PATH, 'INFO', 'Found 1 courses with self-paced runs.'),
                (LOGGER_PATH, 'INFO', f'Scheduling deadline email for course {self.non_draft_course.title} ({self.non_draft_course.key}).'),
                (LOGGER_PATH, 'INFO', f'Deadline email has been scheduled for course {self.non_draft_course.title} ({self.non_draft_course.key}).'),
                (LOGGER_PATH, 'INFO', 'Scheduled course deadline emails for:\n' f"- {self.non_draft_course.title} ({self.non_draft_course.uuid})"),
            )
        # pylint: enable=line-too-long

        mock_apply_async.assert_called_once()
        _, called_kwargs = mock_apply_async.call_args

        expected_args = [
            str(self.non_draft_course.key),
            str(self.non_draft_course_run.key),
            list(set([self.user.email, self.user.email])),
            expected_deadline_variant
        ]

        self.assertEqual(called_kwargs['args'], expected_args)

    def test_with_course_run_with_end_date_within_range_but_with_scheduled_run_in_place(self):
        """
        Test that the command does not send emails when there is an active course run with Scheduled status
        """
        self.non_draft_course_run.end = timezone.now() + timedelta(days=7)
        self.non_draft_course_run.save()
        scheduled_run = CourseRunFactory(
            course=self.non_draft_course,
            status=CourseRunStatus.Reviewed,
            pacing_type=CourseRunPacing.Self,
            start=timezone.now() + timedelta(days=7),
            end=timezone.now() + timedelta(days=100),
            draft=False,
        )
        SeatFactory(
            course_run=scheduled_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=timezone.now() + timedelta(days=100)
        )

        with LogCapture(LOGGER_PATH) as log_capture:
            self.run_command()

            log_capture.check(
                (LOGGER_PATH, 'INFO', "Initializing course deadline email management command."),
                (LOGGER_PATH, 'INFO', 'Found 1 courses with self-paced runs.'),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Course {self.non_draft_course.title} ({self.non_draft_course.key}) "
                    f"has an active course run with status Scheduled."),
                (LOGGER_PATH, 'INFO', "No courses with deadline within the specified range were found."),
            )

    def test_with_course_run_just_ended(self):
        """
        Test that the command sends emails when there is a course run that just ended.
        """
        self.non_draft_course_run.start = timezone.now() - timedelta(days=10)
        self.non_draft_course_run.end = timezone.now() - timedelta(days=1)
        self.non_draft_course_run.status = CourseRunStatus.Unpublished
        self.non_draft_course_run.save()

        with LogCapture(LOGGER_PATH) as log_capture:
            self.run_command()

            log_capture.check(
                (LOGGER_PATH, 'INFO', "Initializing course deadline email management command."),
                (LOGGER_PATH, 'INFO', 'Found 1 courses with self-paced runs.'),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Scheduling deadline email for course '
                    f'{self.non_draft_course.title} ({self.non_draft_course.key}).'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Deadline email has been scheduled for course '
                    f'{self.non_draft_course.title} ({self.non_draft_course.key}).'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    'Scheduled course deadline emails for:\n'
                    f"- {self.non_draft_course.title} ({self.non_draft_course.uuid})"
                ),
            )
