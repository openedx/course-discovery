from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory


class NotifyVerticalAssignmentTests(TestCase):
    """Tests for the Vertical and Sub-vertical notifications."""

    def setUp(self):
        self.group_name = settings.VERTICALS_MANAGEMENT_GROUPS[0]

    @mock.patch("course_discovery.apps.tagging.signals.send_email_for_course_vertical_assignment")
    def test_notify_vertical_assignment_email_sent(self, mock_send_email):
        """
        Test that an email is sent to all members of the groups defined in VERTICALS_MANAGEMENT_GROUPS
        when a new non-draft course entry is created.
        """
        group = Group.objects.create(name=self.group_name)
        user1 = User.objects.create_user(username="user1", email="user1@example.com")
        user2 = User.objects.create_user(username="user2", email="user2@example.com")
        group.user_set.add(user1, user2)

        course = CourseFactory(draft=True)

        mock_send_email.assert_not_called()

        course_run = CourseRunFactory(draft=True, course=course, status=CourseRunStatus.Unpublished)
        course_run.status = CourseRunStatus.Reviewed
        course_run.save()

        expected_recipients = [user1, user2]
        mock_send_email.assert_called_once()
        called_args = mock_send_email.call_args[0]
        self.assertEqual(called_args[0].uuid, course.uuid)
        self.assertListEqual(called_args[1], expected_recipients)

    @mock.patch("course_discovery.apps.tagging.signals.send_email_for_course_vertical_assignment")
    def test_notify_vertical_assignment_email_when_course_is_draft(self, mock_send_email):
        """
        Test that no email is sent when a course is in draft status.
        """
        group = Group.objects.create(name=self.group_name)
        user1 = User.objects.create_user(username="user1", email="user1@example.com")
        user2 = User.objects.create_user(username="user2", email="user2@example.com")
        group.user_set.add(user1, user2)

        CourseFactory(draft=True)

        mock_send_email.assert_not_called()

    @mock.patch("course_discovery.apps.tagging.signals.send_email_for_course_vertical_assignment")
    def test_notify_vertical_assignment_no_group_members(self, mock_send_email):
        """
        Ensure no email is sent when there are no members in the groups defined in VERTICALS_MANAGEMENT_GROUPS.
        """
        Group.objects.create(name=self.group_name)

        course = CourseFactory(draft=True)

        course_run = CourseRunFactory(draft=True, course=course, status=CourseRunStatus.Unpublished)
        course_run.status = CourseRunStatus.Reviewed
        course_run.save()

        mock_send_email.assert_not_called()
