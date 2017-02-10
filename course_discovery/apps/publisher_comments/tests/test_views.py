from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


# pylint: disable=no-member
class CommentsTests(TestCase):
    """ Tests for the Comment functionality on `Courser`, `CourseRun` And `Seat` edit pages. """
    def setUp(self):
        super(CommentsTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.organization_extension = factories.OrganizationExtensionFactory()

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.course_edit_page = 'publisher:publisher_courses_edit'
        self.course_run_edit_page = 'publisher:publisher_course_runs_edit'
        self.seat_edit_page = 'publisher:publisher_seats_edit'
        self.edit_comment_page = 'publisher_comments:comment_edit'

        self.seat = factories.SeatFactory(type=Seat.PROFESSIONAL, credit_hours=0)
        self.course_run = self.seat.course_run
        self.course = self.course_run.course
        self.course.organizations.add(self.organization_extension.organization)

        # assign the role against a course
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )

        toggle_switch('enable_publisher_email_notifications', True)

    def test_comment_edit_with_seat(self):
        """ Verify that only comments attached with specific seat appears on edited page. """
        comments = self._generate_comments_for_all_content_types()
        response = self.client.get(reverse(self.seat_edit_page, kwargs={'pk': self.seat.id}))
        self.assertContains(response, comments.get(self.seat).comment)
        self.assertNotContains(response, comments.get(self.course).comment)
        self.assertNotContains(response, comments.get(self.course_run).comment)

    def test_edit_course_comment(self):
        """ Verify that course comment can be edited. """
        self._edit_comment_page(
            self.course, reverse(self.course_edit_page, kwargs={'pk': self.course.id})
        )

    def test_edit_seat_comment(self):
        """ Verify that seat comment can be edited. """
        self._edit_comment_page(
            self.seat, reverse(self.seat_edit_page, kwargs={'pk': self.seat.id})
        )

    def test_mail_outbox_count(self):
        """ Verify that separate emails send for adding and editing the comment . """
        self._edit_comment_page(
            self.course, reverse(self.course_edit_page, kwargs={'pk': self.course.id})
        )

        # mail has 2 emails one due to newly added comment and other is due to editing.
        self.assertEqual(len(mail.outbox), 2)

    def test_edit_comment_of_other_user(self):
        """ Verify that comment can be edited by the comment author only. """
        comment = self._generate_comment(content_object=self.course, user=self.user)
        comment_url = reverse(self.edit_comment_page, kwargs={'pk': comment.id})
        response = self.client.get(comment_url)
        self.assertEqual(response.status_code, 200)

        # logout and login with other user.
        self.client.logout()
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=user.username, password=USER_PASSWORD)
        response = self.client.get(reverse(self.edit_comment_page, kwargs={'pk': comment.id}))
        self.assertEqual(response.status_code, 404)

    def _edit_comment_page(self, content_object, expected_url):
        """ DRY method for posting the edited comment."""
        comment = self._generate_comment(content_object=content_object, user=self.user)
        comment_url = reverse(self.edit_comment_page, kwargs={'pk': comment.id})

        response = self.client.get(comment_url)
        self._assert_edit_comment(response, comment)

        new_comment = "This is updated comment"
        content_object_dict = model_to_dict(comment)
        content_object_dict['comment'] = new_comment
        response = self.client.post(comment_url, content_object_dict)
        self.assertRedirects(
            response,
            expected_url=expected_url,
            status_code=302, target_status_code=200
        )

        response = self.client.get(comment_url)
        self.assertContains(response, new_comment)

    def _generate_comment(self, content_object, user):
        """ DRY method to generate the comment."""
        return CommentFactory(content_object=content_object, user=user, site=self.site)

    def _assert_edit_comment(self, response, comment):
        """ DRY method for asserting the edited comment page."""
        self.assertContains(response, 'Edit Comment')
        self.assertContains(response, 'Submit date')
        self.assertContains(response, comment.comment)
        self.assertContains(response, comment.submit_date)

        # assert the customize fields exists in comment object
        self.assertTrue(hasattr(comment, 'modified'))

    def _generate_comments_for_all_content_types(self):
        """ DRY method generate the comments for all available content types"""
        data = {}
        for content in [self.course, self.course_run, self.seat]:
            data[content] = self._generate_comment(content_object=content, user=self.user)

        return data

    def _add_assert_multiple_comments(self, content_object, page_path):
        """ DRY method to add comments on edit page for specific object. """
        response = self.client.get(reverse(page_path, kwargs={'pk': content_object.id}))
        self.assertContains(response, 'Total Comments 0')

        comments = []
        for __ in range(1, 2):
            comments.append(self._generate_comment(content_object=content_object, user=self.user))

        # assert emails send
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.get(reverse(page_path, kwargs={'pk': content_object.id}))
        for comment in comments:
            self.assertContains(response, comment.comment)

        self.assertContains(response, 'Total Comments 1')
