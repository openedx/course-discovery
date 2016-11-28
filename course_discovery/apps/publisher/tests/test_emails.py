# pylint: disable=no-member
import datetime
import ddt
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.core import mail
import pytz
import mock
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher import emails
from course_discovery.apps.publisher.models import State
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory


@ddt.ddt
class StateChangeEmailTests(TestCase):
    """ Tests for the Email functionality for course run state changes. """

    @classmethod
    def setUpClass(cls):
        super(StateChangeEmailTests, cls).setUpClass()
        cls.user = UserFactory()
        cls.user_2 = UserFactory()
        cls.user_3 = UserFactory()

        cls.site = Site.objects.get(pk=settings.SITE_ID)

        cls.group_organization_1 = factories.GroupOrganizationFactory()

        # assign users a group
        cls.user.groups.add(cls.group_organization_1.group)
        cls.user_2.groups.add(cls.group_organization_1.group)
        cls.user_3.groups.add(cls.group_organization_1.group)

        cls.seat = factories.SeatFactory()
        cls.course_run = cls.seat.course_run
        cls.course = cls.course_run.course

        # adding the course organization
        cls.course.organizations.add(cls.group_organization_1.organization)
        # NOTE: We intentionally do NOT create an attribute for user_2.
        # By default this user WILL receive email notifications.

        UserAttributeFactory(user=cls.user, enable_email_notification=True)
        UserAttributeFactory(user=cls.user_3, enable_email_notification=False)

        toggle_switch('enable_publisher_email_notifications', True)

    @mock.patch('course_discovery.apps.publisher.models.send_email_for_change_state')
    def test_email_with_enable_waffle_switch(self, send_email_for_change_state):
        """ Verify that send_email_for_state called with enable waffle switch.. """
        self.course_run.change_state(target=State.DRAFT)
        send_email_for_change_state.assert_called_once_with(self.course_run)

    @mock.patch('course_discovery.apps.publisher.models.send_email_for_change_state')
    def test_email_with_waffle_switch_disabled(self, send_email_for_change_state):
        """ Verify that send_email_for_state not called with disable waffle switch.. """
        toggle_switch('enable_publisher_email_notifications', False)
        self.course_run.change_state(target=State.DRAFT)
        send_email_for_change_state.assert_not_called()

    def _assert_data(self):
        """ DRY method to assert send email data"""
        self.assertEqual([self.user.email, self.user_2.email], mail.outbox[0].to)

        subject = 'Course Run {title}-{pacing_type}-{start} state has been changed.'.format(
            title=self.course_run.course.title,
            pacing_type=self.course_run.get_pacing_type_display(),
            start=self.course_run.start.strftime("%B %d, %Y")
        )
        body = mail.outbox[0].body.strip()
        self.assertEqual(
            str(mail.outbox[0].subject),
            subject
        )
        self.assertIn('Hi', body)
        self.assertIn('The edX team', body)
        'The following course run has been submitted for {{ state }}'.format(
            state=self.course_run.state.name
        )

        page_path = reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=page_path)
        self.assertIn(page_url, body)

    @ddt.data(
        State.DRAFT, State.NEEDS_REVIEW, State.NEEDS_FINAL_APPROVAL,
        State.FINALIZED, State.PUBLISHED, State.DRAFT
    )
    def test_email_without_group(self, target_state):
        """ Verify that no email send if course group has no users. """
        self.user.groups.remove(self.group_organization_1.group)
        self.user_2.groups.remove(self.group_organization_1.group)
        self.user_3.groups.remove(self.group_organization_1.group)

        self.course_run.change_state(target=target_state)
        self.assertEqual(len(mail.outbox), 0)

    @ddt.data(
        State.DRAFT, State.NEEDS_REVIEW, State.NEEDS_FINAL_APPROVAL,
        State.FINALIZED, State.PUBLISHED, State.DRAFT
    )
    def test_workflow_change_state_emails(self, target_state):
        """ Verify that on each state change an email send to course group users. """
        self.course_run.change_state(target=target_state)
        self.assertEqual(len(mail.outbox), 1)
        self._assert_data()

    def test_email_without_start_date(self):
        """ Verify that emails works properly even if course run does not have
        start date.
        """
        self.course_run.start = None
        self.course_run.save()
        self.course_run.change_state(target=State.DRAFT)
        self.assertEqual(len(mail.outbox), 1)

        # add the start date again for other tests.
        self.course_run.start = datetime.datetime.now(pytz.UTC)
        self.course_run.save()


class StudioInstanceCreatedEmailTests(TestCase):
    """ Tests for the email functionality for studio instance created. """

    def setUp(self):
        super(StudioInstanceCreatedEmailTests, self).setUp()
        self.user = UserFactory()
        self.group_organization_1 = factories.GroupOrganizationFactory()
        self.user.groups.add(self.group_organization_1.group)

        self.course_run = factories.CourseRunFactory()

        self.course_run.course.organizations.add(self.group_organization_1.organization)

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

        # assert email sent
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio instance created',
            'Studio instance created for the following course run'
        )

    def assert_email_sent(self, object_path, subject, expected_body):
        """ DRY method to assert sent email data"""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([settings.PUBLISHER_FROM_EMAIL], mail.outbox[0].to)
        self.assertEqual([self.user.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)
