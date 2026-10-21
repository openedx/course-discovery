import logging
from unittest import mock

from django.conf import settings
from django.core import mail
from django.test import TestCase

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory
from course_discovery.apps.tagging.emails import send_email_for_course_vertical_assignment


class VerticalAssignmentEmailTests(TestCase):
    """Tests for the Vertical and Sub-vertical email."""

    def setUp(self):
        self.group_name = settings.VERTICALS_MANAGEMENT_GROUPS[0]
        self.course = CourseFactory(title="Test Course", draft=False)
        self.user1 = UserFactory(email="user1@example.com")
        self.user2 = UserFactory(email="user2@example.com")
        self.recipients = [self.user1, self.user2]
        self.logger = logging.getLogger("course_discovery.apps.tagging.emails")

    def test_email_sent_to_recipients(self):
        """
        Test that an email is sent to the specified recipients with the correct subject.
        """
        send_email_for_course_vertical_assignment(self.course, self.recipients)

        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, [self.user1.email, self.user2.email])
        expected_subject = f"Action Required: Assign Vertical and Sub-vertical for Course '{self.course.title}'"
        self.assertEqual(email.subject, expected_subject)

    @mock.patch("course_discovery.apps.tagging.emails.EmailMessage.send")
    def test_email_send_failure_logs_exception(self, mock_send):
        """
        Test that an exception is logged if the email fails to send.
        """
        mock_send.side_effect = Exception("Email sending failed")

        with self.assertLogs(logger=self.logger, level="ERROR") as log_context:
            send_email_for_course_vertical_assignment(self.course, self.recipients)

        self.assertIn("Failed to send vertical assignment email", log_context.output[0])

    def test_no_email_sent_when_user_notifications_disabled(self):
        """
        Test that if a user has disabled email notifications via their UserAttributes,
        then no email is sent.
        """

        disabled_user = UserFactory(email="disabled@example.com")
        UserAttributeFactory(user=disabled_user, enable_email_notification=False)

        send_email_for_course_vertical_assignment(self.course, [disabled_user])

        with self.assertLogs(logger=self.logger, level="ERROR") as log_context:
            send_email_for_course_vertical_assignment(self.course, [disabled_user])

        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("No recipients found.", log_context.output[0])
