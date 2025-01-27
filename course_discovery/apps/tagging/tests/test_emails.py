import logging
from unittest import mock

from django.conf import settings
from django.core import mail
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.emails import send_email_for_course_vertical_assignment


class VerticalAssignmentEmailTests(TestCase):
    """Tests for the Vertical and Sub-vertical email."""

    def setUp(self):
        self.group_name = settings.VERTICALS_MANAGEMENT_GROUPS[0]
        self.course = CourseFactory(title="Test Course", draft=False)
        self.recipients = ["user1@example.com", "user2@example.com"]
        self.logger = logging.getLogger("course_discovery.apps.tagging.emails")

    def test_email_sent_to_recipients(self):
        """
        Test that an email is sent to the specified recipients with the correct subject
        """
        send_email_for_course_vertical_assignment(self.course, self.recipients)

        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertEqual(email.to, self.recipients)
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
