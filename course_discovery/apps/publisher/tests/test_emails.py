# pylint: disable=no-member

import mock
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from opaque_keys.edx.keys import CourseKey
from testfixtures import LogCapture

from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher import emails
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import LEGAL_TEAM_GROUP_NAME
from course_discovery.apps.publisher.models import UserAttributes
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory


class StudioInstanceCreatedEmailTests(TestCase):
    """
    Tests for the studio instance created email functionality.
    """

    def setUp(self):
        super(StudioInstanceCreatedEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_run = factories.CourseRunFactory(lms_course_id='course-v1:edX+DemoX+Demo_Course')

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )

        self.course_team = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam, user=self.course_team
        )

        UserAttributeFactory(user=self.user, enable_email_notification=True)

        toggle_switch('enable_publisher_email_notifications', True)

    @mock.patch('django.core.mail.message.EmailMessage.send', mock.Mock(side_effect=TypeError))
    def test_email_with_error(self):
        """ Verify that emails failure raise exception."""

        with self.assertRaises(Exception) as ex:
            emails.send_email_for_studio_instance_created(self.course_run)
            error_message = 'Failed to send email notifications for course_run [{}]'.format(self.course_run.id)
            self.assertEqual(ex.message, error_message)

    def test_email_sent_successfully(self):
        """ Verify that emails sent successfully for studio instance created."""

        emails.send_email_for_studio_instance_created(self.course_run)
        course_key = CourseKey.from_string(self.course_run.lms_course_id)
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio URL created: {title} {run_number}'.format(
                title=self.course_run.course.title,
                run_number=course_key.run
            ),
            'created a Studio URL for the'
        )

    def assert_email_sent(self, object_path, subject, expected_body):
        """ Assert email data"""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course_team.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)
        self.assertIn('Enter course run content in Studio.', body)
        self.assertIn('Thanks', body)
        self.assertIn('This email address is unable to receive replies. For questions or comments', body)
        self.assertIn(self.course_team.full_name, body)
        self.assertIn(self.user.full_name, body)
        self.assertIn('Note: This email address is unable to receive replies.', body)
        self.assertIn(
            'For questions or comments, contact {}.'.format(self.user.email), body
        )


class CourseCreatedEmailTests(TestCase):
    """ Tests for the new course created email functionality. """

    def setUp(self):
        super(CourseCreatedEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_run = factories.CourseRunFactory()

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )

        self.course_team = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam, user=self.course_team
        )

        UserAttributeFactory(user=self.user, enable_email_notification=True)

        toggle_switch('enable_publisher_email_notifications', True)

    @mock.patch('django.core.mail.message.EmailMessage.send', mock.Mock(side_effect=TypeError))
    def test_email_with_error(self):
        """ Verify that emails failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_course_creation(self.course_run.course, self.course_run)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications for creation of course [{}]'.format(
                        self.course_run.course.id
                    )
                )
            )

    def test_email_sent_successfully(self):
        """ Verify that studio instance request email sent successfully."""

        emails.send_email_for_course_creation(self.course_run.course, self.course_run)
        subject = 'Studio URL requested: {title}'.format(title=self.course_run.course.title)
        self.assert_email_sent(subject)

    def assert_email_sent(self, subject):
        """ Assert email data."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.user.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn('{name} created the'.format(name=self.course_team.full_name), body)
        self.assertIn('{dashboard_url}'.format(dashboard_url=reverse('publisher:publisher_dashboard')), body)
        self.assertIn('Please create a Studio URL for this course.', body)
        self.assertIn('Thanks', body)

    def test_email_not_sent_with_notification_disabled(self):
        """ Verify that emails not sent if notification disabled by user."""
        user_attribute = UserAttributes.objects.get(user=self.user)
        user_attribute.enable_email_notification = False
        user_attribute.save()
        emails.send_email_for_course_creation(self.course_run.course, self.course_run)

        self.assertEqual(len(mail.outbox), 0)


class SendForReviewEmailTests(TestCase):
    """ Tests for the send for review email functionality. """

    def setUp(self):
        super(SendForReviewEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_state = factories.CourseStateFactory()

    def test_email_with_error(self):
        """ Verify that email failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_send_for_review(self.course_state.course, self.user)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications send for review of course {}'.format(
                        self.course_state.course.id
                    )
                )
            )


class CourseMarkAsReviewedEmailTests(TestCase):
    """ Tests for the mark as reviewed email functionality. """

    def setUp(self):
        super(CourseMarkAsReviewedEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_state = factories.CourseStateFactory()

    def test_email_with_error(self):
        """ Verify that email failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_mark_as_reviewed(self.course_state.course, self.user)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications mark as reviewed of course {}'.format(
                        self.course_state.course.id
                    )
                )
            )


class CourseRunSendForReviewEmailTests(TestCase):
    """ Tests for the CourseRun send for review email functionality. """

    def setUp(self):
        super(CourseRunSendForReviewEmailTests, self).setUp()
        self.user = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.seat = factories.SeatFactory()
        self.course_run = self.seat.course_run
        self.course = self.course_run.course
        self.course.organizations.add(OrganizationFactory())

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user_2
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=self.user_3
        )
        self.course_run_state = factories.CourseRunStateFactory(course_run=self.course_run)
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.save()

        self.course_key = CourseKey.from_string(self.course_run.lms_course_id)

        toggle_switch('enable_publisher_email_notifications', True)

    def test_email_sent_by_marketing_reviewer(self):
        """ Verify that email works successfully for marketing user."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        emails.send_email_for_send_for_review_course_run(self.course_run_state.course_run, self.user)
        subject = 'Review requested: {title} {run_number}'.format(title=self.course, run_number=self.course_key.run)
        self.assert_email_sent(subject, self.user_2)

    def test_email_sent_by_course_team(self):
        """ Verify that email works successfully for course team user."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        emails.send_email_for_send_for_review_course_run(self.course_run_state.course_run, self.user_2)
        subject = 'Review requested: {title} {run_number}'.format(title=self.course, run_number=self.course_key.run)
        self.assert_email_sent(subject, self.user)

    def test_email_with_error(self):
        """ Verify that email failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_send_for_review_course_run(self.course_run, self.user)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications send for review of course-run {}'.format(
                        self.course_run.id
                    )
                )
            )

    def assert_email_sent(self, subject, to_email):
        """ Assert email data."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(to_email.email, mail.outbox[0].to[0])
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('View this course run in Publisher to review the changes or suggest edits.', body)


class CourseRunMarkAsReviewedEmailTests(TestCase):
    """ Tests for the CourseRun mark as reviewed email functionality. """

    def setUp(self):
        super(CourseRunMarkAsReviewedEmailTests, self).setUp()
        self.user = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.seat = factories.SeatFactory()
        self.course_run = self.seat.course_run
        self.course = self.course_run.course
        self.course.organizations.add(OrganizationFactory())

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user_2
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=self.user_3
        )
        self.course_run_state = factories.CourseRunStateFactory(course_run=self.course_run)

        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.save()

        toggle_switch('enable_publisher_email_notifications', True)

    def test_email_not_sent_by_project_coordinator(self):
        """ Verify that no email is sent if approving person is project coordinator. """
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        emails.send_email_for_mark_as_reviewed_course_run(self.course_run_state.course_run, self.user)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_sent_by_course_team(self):
        """ Verify that email works successfully for course team user."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        emails.send_email_for_mark_as_reviewed_course_run(self.course_run_state.course_run, self.user_2)
        self.assert_email_sent(self.user)

    def test_email_mark_as_reviewed_with_error(self):
        """ Verify that email failure log error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_mark_as_reviewed_course_run(self.course_run, self.user)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications for mark as reviewed of course-run {}'.format(
                        self.course_run.id
                    )
                )
            )

    def test_email_sent_to_publisher(self):
        """ Verify that email works successfully."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        emails.send_email_to_publisher(self.course_run_state.course_run, self.user)
        self.assert_email_sent(self.user_3)

    def test_email_to_publisher_with_error(self):
        """ Verify that email failure log error message."""

        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with LogCapture(emails.logger.name) as l:
                emails.send_email_to_publisher(self.course_run, self.user_3)
                l.check(
                    (
                        emails.logger.name,
                        'ERROR',
                        'Failed to send email notifications for mark as reviewed of course-run {}'.format(
                            self.course_run.id
                        )
                    )
                )

    def assert_email_sent(self, to_email):
        """ Verify the email data for tests cases."""

        course_key = CourseKey.from_string(self.course_run.lms_course_id)
        subject = 'Review complete: {course_name} {run_number}'.format(
            course_name=self.course.title,
            run_number=course_key.run
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(to_email.email, mail.outbox[0].to[0])
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('The review for this course run is complete.', body)


class CourseRunPreviewEmailTests(TestCase):
    """
    Tests for the course preview email functionality.
    """

    def setUp(self):
        super(CourseRunPreviewEmailTests, self).setUp()
        self.user = UserFactory()

        self.run_state = factories.CourseRunStateFactory()
        self.course = self.run_state.course_run.course

        self.course.organizations.add(OrganizationFactory())

        # add users in CourseUserRole table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=UserFactory()
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=UserFactory()
        )

        toggle_switch('enable_publisher_email_notifications', True)

    def test_preview_accepted_email(self):
        """
        Verify that preview accepted email functionality works fine.
        """
        lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.run_state.course_run.lms_course_id = lms_course_id

        emails.send_email_preview_accepted(self.run_state.course_run)

        course_key = CourseKey.from_string(lms_course_id)
        subject = 'Publication requested: {course_name} {run_number}'.format(
            course_name=self.course.title,
            run_number=course_key.run
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.publisher.email, self.course.project_coordinator.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.run_state.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('You can now publish this About page.', body)

    def test_preview_accepted_email_with_error(self):
        """ Verify that email failure log error message."""

        message = 'Failed to send email notifications for preview approved of course-run [{}]'.format(
            self.run_state.course_run.id
        )
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with self.assertRaises(Exception) as ex:
                self.assertEqual(str(ex.exception), message)
                with LogCapture(emails.logger.name) as l:
                    emails.send_email_preview_accepted(self.run_state.course_run)
                    l.check(
                        (
                            emails.logger.name,
                            'ERROR',
                            message
                        )
                    )

    def test_preview_available_email(self):
        """
        Verify that preview available email functionality works fine.
        """
        course_run = self.run_state.course_run
        course_run.lms_course_id = 'course-v1:testX+testX1.0+2017T1'
        course_run.save()

        emails.send_email_preview_page_is_available(course_run)

        course_key = CourseKey.from_string(course_run.lms_course_id)
        subject = 'Review requested: Preview for {course_name} {run_number}'.format(
            course_name=self.course.title,
            run_number=course_key.run
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.course_team_admin.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('A preview is now available for the', body)

    def test_preview_available_email_with_error(self):
        """ Verify that exception raised on email failure."""

        with self.assertRaises(Exception) as ex:
            emails.send_email_preview_page_is_available(self.run_state.course_run)
            error_message = 'Failed to send email notifications for preview available of course-run {}'.format(
                self.run_state.course_run.id
            )
            self.assertEqual(ex.message, error_message)

    def test_preview_available_email_with_notification_disabled(self):
        """ Verify that email not sent if notification disabled by user."""
        factories.UserAttributeFactory(user=self.course.course_team_admin, enable_email_notification=False)
        emails.send_email_preview_page_is_available(self.run_state.course_run)

        self.assertEqual(len(mail.outbox), 0)

    def test_preview_accepted_email_with_notification_disabled(self):
        """ Verify that preview accepted email not sent if notification disabled by user."""
        factories.UserAttributeFactory(user=self.course.publisher, enable_email_notification=False)
        emails.send_email_preview_accepted(self.run_state.course_run)

        self.assertEqual(len(mail.outbox), 0)


class CourseRunPublishedEmailTests(TestCase):
    """
    Tests for course run published email functionality.
    """

    def setUp(self):
        super(CourseRunPublishedEmailTests, self).setUp()
        self.user = UserFactory()

        self.run_state = factories.CourseRunStateFactory()
        self.course_run = self.run_state.course_run
        self.course = self.course_run.course

        # add users in CourseUserRole table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=UserFactory()
        )

        toggle_switch('enable_publisher_email_notifications', True)

    def test_course_published_email(self):
        """
        Verify that course published email functionality works fine.
        """
        self.course_run.lms_course_id = 'course-v1:testX+test45+2017T2'
        self.course_run.save()
        emails.send_course_run_published_email(self.course_run)

        course_key = CourseKey.from_string(self.course_run.lms_course_id)
        subject = 'Publication complete: About page for {course_name} {run_number}'.format(
            course_name=self.course_run.course.title,
            run_number=course_key.run
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.course_team_admin.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        self.assertIn(self.course_run.preview_url, body)
        self.assertIn(self.course_run.preview_url, body)
        self.assertIn('has been published', body)

    def test_course_published_email_with_error(self):
        """ Verify that email failure log error message."""

        message = 'Failed to send email notifications for course published of course-run [{}]'.format(
            self.course_run.id
        )
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with self.assertRaises(Exception) as ex:
                emails.send_course_run_published_email(self.course_run)
                self.assertEqual(str(ex.exception), message)


class CourseChangeRoleAssignmentEmailTests(TestCase):
    """
    Tests email functionality for course role assignment changed.
    """

    def setUp(self):
        super(CourseChangeRoleAssignmentEmailTests, self).setUp()
        self.user = UserFactory()

        self.marketing_role = factories.CourseUserRoleFactory(role=PublisherUserRole.MarketingReviewer, user=self.user)
        self.course = self.marketing_role.course
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator)
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.CourseTeam)

        toggle_switch('enable_publisher_email_notifications', True)

    def test_change_role_assignment_email(self):
        """
        Verify that course role assignment chnage email functionality works fine.
        """
        emails.send_change_role_assignment_email(self.marketing_role, self.user)
        expected_subject = '{role_name} changed for {course_title}'.format(
            role_name=self.marketing_role.get_role_display().lower(),
            course_title=self.course.title
        )

        expected_emails = set(self.course.get_course_users_emails())
        expected_emails.remove(self.course.course_team_admin.email)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(expected_emails, set(mail.outbox[0].to))
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('has changed.', body)

    def test_change_role_assignment_email_with_error(self):
        """
        Verify that email failure raises exception.
        """

        message = 'Failed to send email notifications for change role assignment of role: [{role_id}]'.format(
            role_id=self.marketing_role.id
        )
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with self.assertRaises(Exception) as ex:
                emails.send_change_role_assignment_email(self.marketing_role, self.user)
                self.assertEqual(str(ex.exception), message)


class SEOReviewEmailTests(TestCase):
    """ Tests for the seo review email functionality. """

    def setUp(self):
        super(SEOReviewEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_state = factories.CourseStateFactory()
        self.course = self.course_state.course
        self.course.organizations.add(OrganizationFactory())
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.CourseTeam, user=self.user)
        self.legal_user = UserFactory()
        self.legal_user.groups.add(Group.objects.get(name=LEGAL_TEAM_GROUP_NAME))

        UserAttributeFactory(user=self.user, enable_email_notification=True)

    def test_email_with_error(self):
        """ Verify that email failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_seo_review(self.course)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications for legal review requested of course {}'.format(
                        self.course.id
                    )
                )
            )

    def test_seo_review_email(self):
        """
        Verify that seo review email functionality works fine.
        """
        factories.CourseUserRoleFactory(course=self.course, role=PublisherUserRole.ProjectCoordinator)
        emails.send_email_for_seo_review(self.course)
        expected_subject = 'Legal review requested: {title}'.format(title=self.course.title)

        self.assertEqual(len(mail.outbox), 1)
        legal_team_users = User.objects.filter(groups__name=LEGAL_TEAM_GROUP_NAME)
        expected_addresses = [user.email for user in legal_team_users]
        self.assertEqual(expected_addresses, mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('determine OFAC status', body)


class CourseRunPublishedEditEmailTests(CourseRunPublishedEmailTests):
    """
    Tests for published course-run editing email functionality.
    """

    def test_published_course_run_editing_email(self):
        """
        Verify that on edit the published course-run email send to publisher.
        """
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.ProjectCoordinator, user=self.user
        )
        self.course_run.lms_course_id = 'course-v1:testX+test45+2017T2'
        self.course_run.save()
        emails.send_email_for_published_course_run_editing(self.course_run)

        course_key = CourseKey.from_string(self.course_run.lms_course_id)

        subject = 'Changes to published course run: {title} {run_number}'.format(
            title=self.course_run.course.title,
            run_number=course_key.run
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.publisher.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        self.assertIn('has made changes to the following published course run.', body)
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.run_state.course_run.id})
        self.assertIn(page_path, body)

    def test_email_with_error(self):
        """ Verify that email failure logs error message."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_published_course_run_editing(self.course_run)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications for publisher course-run [{}] editing.'.format(
                        self.course_run.id
                    )
                )
            )
