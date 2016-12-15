import ddt
import mock
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.models import Course
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


@ddt.ddt
class CommentsEmailTests(TestCase):
    """ Tests for the e-mail functionality for course, course-run and seats. """

    def setUp(self):
        super(CommentsEmailTests, self).setUp()

        self.user = UserFactory()
        self.user_2 = UserFactory()
        self.user_3 = UserFactory()

        self.site = Site.objects.get(pk=settings.SITE_ID)

        self.organization_extension = factories.OrganizationExtensionFactory()

        self.user.groups.add(self.organization_extension.group)
        self.user_2.groups.add(self.organization_extension.group)
        self.user_3.groups.add(self.organization_extension.group)

        self.seat = factories.SeatFactory()
        self.course_run = self.seat.course_run
        self.course = self.course_run.course

        self.course.organizations.add(self.organization_extension.organization)
        assign_perm(Course.VIEW_PERMISSION, self.organization_extension.group, self.course)

        # NOTE: We intentionally do NOT create an attribute for user_2.
        # By default this user WILL receive email notifications.

        UserAttributeFactory(user=self.user, enable_email_notification=True)
        UserAttributeFactory(user=self.user_3, enable_email_notification=False)
        toggle_switch('enable_publisher_email_notifications', True)

    def test_course_comment_email(self):
        """ Verify that after adding a comment against a course emails send
        to multiple users depending upon the course related group.
        """
        comment = self.create_comment(content_object=self.course)
        subject = 'New comment added in Course: {title}'.format(title=self.course.title)
        self.assert_comment_email_sent(
            self.course, comment, reverse('publisher:publisher_courses_edit', args=[self.course.id]),
            subject
        )

    def test_course_run_comment_email(self):
        """ Verify that after adding a comment against a course-run emails send to multiple users
        depending upon the parent course related group.
        """
        comment = self.create_comment(content_object=self.course_run)
        subject = 'New comment added in course run: {title}-{pacing_type}-{start}'.format(
            title=self.course_run.course.title,
            pacing_type=self.course_run.get_pacing_type_display(),
            start=self.course_run.start.strftime('%B %d, %Y')
        )
        self.assert_comment_email_sent(
            self.course_run, comment,
            reverse('publisher:publisher_course_run_detail', args=[self.course_run.id]),
            subject
        )

    @mock.patch('course_discovery.apps.publisher_comments.models.send_email_for_comment')
    def test_email_with_enable_waffle_switch(self, send_email_for_comment):
        """ Verify that send_email_for_comment called with enable waffle switch.. """
        comment = self.create_comment(content_object=self.course)
        send_email_for_comment.assert_called_once_with(comment)

    @mock.patch('course_discovery.apps.publisher_comments.models.send_email_for_comment')
    def test_email_with_disable_waffle_switch(self, send_email_for_comment):
        """ Verify that send_email_for_comment not called with disable waffle switch.. """
        toggle_switch('enable_publisher_email_notifications', False)
        self.create_comment(content_object=self.course)
        send_email_for_comment.assert_not_called()

    def test_email_without_different_group(self):
        """ Verify the emails behaviour if course group has no users. """
        self.user.groups.remove(self.organization_extension.group)
        self.user_2.groups.remove(self.organization_extension.group)
        self.user_3.groups.remove(self.organization_extension.group)
        self.create_comment(content_object=self.course)
        self.assertEqual(len(mail.outbox), 0)

    def test_course_run_without_start_date(self):
        """ Verify that emails works properly even if course-run does not have a start date."""
        self.course_run.start = None
        self.course_run.save()
        comment = self.create_comment(content_object=self.course_run)
        subject = 'New comment added in course run: {title}-{pacing_type}-{start}'.format(
            title=self.course_run.course.title,
            pacing_type=self.course_run.get_pacing_type_display(),
            start=''
        )
        self.assert_comment_email_sent(
            self.course_run, comment,
            reverse('publisher:publisher_course_run_detail', args=[self.course_run.id]),
            subject
        )

    def assert_comment_email_sent(self, content_object, comment, object_path, subject):
        """ DRY method to assert send email data"""
        object_type = content_object.__class__.__name__
        self.assertEqual([self.user.email, self.user_2.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)
        body = mail.outbox[0].body.strip()
        heading = '{first_name} commented on a {object_type} belonging to the course {title} ({number})'
        self.assertIn(
            heading.format(
                first_name=comment.user.first_name, object_type=object_type.lower(),
                title=self.course.title, number=self.course.number
            ),
            body
        )
        page_url = 'https://{host}{path}'.format(host=comment.site.domain.strip('/'), path=object_path)
        self.assertIn(comment.comment, body)
        self.assertIn(page_url, body)
        self.assertIn('The edX team', body)

    def create_comment(self, content_object):
        """ DRY method to create the comment for a given content type."""
        return CommentFactory(
            content_object=content_object, user=self.user, site=self.site
        )
