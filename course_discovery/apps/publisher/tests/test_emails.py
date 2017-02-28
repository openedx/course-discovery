# pylint: disable=no-member

import mock
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher import emails
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory


class StudioInstanceCreatedEmailTests(TestCase):
    """ Tests for the email functionality for studio instance created. """

    def setUp(self):
        super(StudioInstanceCreatedEmailTests, self).setUp()
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
        """ Verify that emails for studio instance created."""

        with LogCapture(emails.logger.name) as l:
            emails.send_email_for_studio_instance_created(self.course_run)
            l.check(
                (
                    emails.logger.name,
                    'ERROR',
                    'Failed to send email notifications for course_run [{}]'.format(self.course_run.id)
                )
            )

    def test_email_sent_successfully(self):
        """ Verify that emails sent successfully for studio instance created."""

        emails.send_email_for_studio_instance_created(self.course_run)
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio instance created',
            'EdX has created a Studio instance for'
        )

    def assert_email_sent(self, object_path, subject, expected_body):
        """ DRY method to assert sent email data"""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([settings.PUBLISHER_FROM_EMAIL], mail.outbox[0].to)
        self.assertEqual([self.user.email, self.course_team.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)
        self.assertIn('You can now edit this course in Studio.', body)
        self.assertIn('Thanks', body)
        self.assertIn('This email address is unable to receive replies. For questions or comments', body)
        self.assertIn(self.course_team.full_name, body)
        self.assertIn(self.user.full_name, body)
        self.assertIn('Note: This email address is unable to receive replies.', body)
        self.assertIn(
            'For questions or comments, contact {}.'.format(self.user.email), body
        )


class CourseCreatedEmailTests(TestCase):
    """ Tests for the email functionality for new course created. """

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
        """ Verify that emails failure log message."""

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
        """ Verify that emails send as course creation notifications."""

        emails.send_email_for_course_creation(self.course_run.course, self.course_run)
        subject = 'New Studio instance request for {title}'.format(title=self.course_run.course.title)
        self.assert_email_sent(subject)

    def assert_email_sent(self, subject):
        """ Verify the email data for tests cases."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.user.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn('{name} created the'.format(name=self.course_team.full_name), body)
        self.assertIn('{dashboard_url}'.format(dashboard_url=reverse('publisher:publisher_dashboard')), body)
        self.assertIn('Please create a Studio instance for this course', body)
        self.assertIn('Thanks', body)


class SendForReviewEmailTests(TestCase):
    """ Tests for the email functionality for send for review. """

    def setUp(self):
        super(SendForReviewEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_state = factories.CourseStateFactory()

    def test_email_with_error(self):
        """ Verify that email failure log error message."""

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
    """ Tests for the email functionality for mark as reviewed. """

    def setUp(self):
        super(CourseMarkAsReviewedEmailTests, self).setUp()
        self.user = UserFactory()
        self.course_state = factories.CourseStateFactory()

    def test_email_with_error(self):
        """ Verify that email failure log error message."""

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
    """ Tests for the email functionality for send for review. """

    def setUp(self):
        super(CourseRunSendForReviewEmailTests, self).setUp()
        self.user = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.seat = factories.SeatFactory()
        self.course_run = self.seat.course_run
        self.course = self.course_run.course

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user_2
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=self.user_3
        )
        self.course_run_state = factories.CourseRunStateFactory(course_run=self.course_run)

        toggle_switch('enable_publisher_email_notifications', True)

    def test_email_sent_by_marketing_reviewer(self):
        """ Verify that email works successfully."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )
        emails.send_email_for_send_for_review_course_run(self.course_run_state.course_run, self.user)
        subject = 'Changes to {title} are ready for review'.format(title=self.course_run.course.title)
        self.assert_email_sent(subject, self.user_2)

    def test_email_sent_by_course_team(self):
        """ Verify that email works successfully."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )
        emails.send_email_for_send_for_review_course_run(self.course_run_state.course_run, self.user_2)
        subject = 'Changes to {title} are ready for review'.format(title=self.course_run.course.title)
        self.assert_email_sent(subject, self.user)

    def test_email_with_error(self):
        """ Verify that email failure log error message."""

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
        """ Verify the email data for tests cases."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(to_email.email, mail.outbox[0].to[0])
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('are ready for your review.', body)


class CourseRunMarkAsReviewedEmailTests(TestCase):
    """ Tests email functionality of mark as reviewed. """

    def setUp(self):
        super(CourseRunMarkAsReviewedEmailTests, self).setUp()
        self.user = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.seat = factories.SeatFactory()
        self.course_run = self.seat.course_run
        self.course = self.course_run.course

        # add user in course-user-role table
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user_2
        )
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.Publisher, user=self.user_3
        )
        self.course_run_state = factories.CourseRunStateFactory(course_run=self.course_run)

        toggle_switch('enable_publisher_email_notifications', True)

    def test_email_sent_by_marketing_reviewer(self):
        """ Verify that email works successfully."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )
        emails.send_email_for_mark_as_reviewed_course_run(self.course_run_state.course_run, self.user)
        self.assert_email_sent(self.user_2)

    def test_email_sent_by_course_team(self):
        """ Verify that email works successfully."""
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
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
        run_name = '{pacing_type}: {start_date}'.format(
            pacing_type=self.course_run.get_pacing_type_display(),
            start_date=self.course_run.start.strftime("%B %d, %Y")
        )
        subject = 'Changes to {run_name} has been marked as reviewed'.format(
            run_name=run_name
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(to_email.email, mail.outbox[0].to[0])
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('has been marked as reviewed.', body)


class CourseRunPreviewEmailTests(TestCase):
    """
    Tests email functionality of course preview.
    """

    def setUp(self):
        super(CourseRunPreviewEmailTests, self).setUp()
        self.user = UserFactory()

        self.run_state = factories.CourseRunStateFactory()
        self.course = self.run_state.course_run.course

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
        emails.send_email_preview_accepted(self.run_state.course_run)
        run_name = '{pacing_type}: {start_date}'.format(
            pacing_type=self.run_state.course_run.get_pacing_type_display(),
            start_date=self.run_state.course_run.start.strftime("%B %d, %Y")
        )
        subject = 'Preview for {run_name} has been approved'.format(
            run_name=run_name
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.publisher.email, self.course.project_coordinator.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.run_state.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('has beed approved by course team.', body)

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
        emails.send_email_preview_page_is_available(self.run_state.course_run)
        run_name = '{pacing_type}: {start_date}'.format(
            pacing_type=self.run_state.course_run.get_pacing_type_display(),
            start_date=self.run_state.course_run.start.strftime("%B %d, %Y")
        )
        subject = 'Preview for {run_name} is available'.format(
            run_name=run_name
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.course_team_admin.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.run_state.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('is available for review.', body)

    def test_preview_available_email_with_error(self):
        """ Verify that email failure log error message."""

        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with LogCapture(emails.logger.name) as l:
                emails.send_email_preview_page_is_available(self.run_state.course_run)
                l.check(
                    (
                        emails.logger.name,
                        'ERROR',
                        'Failed to send email notifications for preview available of course-run {}'.format(
                            self.run_state.course_run.id
                        )
                    )
                )


class CourseRunPublishedEmailTests(TestCase):
    """
    Tests email functionality for course run published.
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
        emails.send_course_run_published_email(self.course_run)
        course_name = '{title}: {pacing_type} - {start_date}'.format(
            title=self.course.title,
            pacing_type=self.course_run.get_pacing_type_display(),
            start_date=self.course_run.start.strftime("%B %d, %Y")
        )
        subject = 'Course {course_name} is now live'.format(course_name=course_name)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.course.course_team_admin.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)
        self.assertIn('is now live.', body)

    def test_course_published_email_with_error(self):
        """ Verify that email failure log error message."""

        message = 'Failed to send email notifications for course published of course-run [{}]'.format(
            self.course_run.id
        )
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=TypeError):
            with self.assertRaises(Exception) as ex:
                emails.send_course_run_published_email(self.course_run)
                self.assertEqual(str(ex.exception), message)
