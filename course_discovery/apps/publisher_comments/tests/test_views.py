from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.forms import model_to_dict
from django.test import TestCase
from django.core import mail
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory
from course_discovery.apps.publisher.tests.factories import UserAttributeFactory


# pylint: disable=no-member
class CommentsTests(TestCase):
    """ Tests for the Comment functionality on `Courser`, `CourseRun` And `Seat` edit pages. """
    def setUp(self):
        super(CommentsTests, self).setUp()
        self.user = UserFactory(email='test@test-edx.org')
        self.group = factories.GroupFactory()
        self.group2 = factories.GroupFactory()
        self.user.groups.add(self.group)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.course_edit_page = 'publisher:publisher_courses_edit'
        self.course_run_edit_page = 'publisher:publisher_course_runs_edit'
        self.seat_edit_page = 'publisher:publisher_seats_edit'
        self.edit_comment_page = 'publisher_comments:comment_edit'
        self.course = factories.CourseFactory()
        self.course_run = factories.CourseRunFactory(course=self.course)
        self.seat = factories.SeatFactory(type=Seat.PROFESSIONAL, credit_hours=0, course_run=self.course_run)
        assign_perm(self.course.VIEW_PERMISSION, self.group, self.course)
        UserAttributeFactory(user=self.user, enable_notification=True)
        toggle_switch('enable_emails', True)

    def _add_attribute(self, user, enable):
        UserAttributeFactory(user=user, enable_notification=enable)

    def test_course_edit_page_with_multiple_comments(self):
        """ Verify course edit page can load multiple comments"""
        self._add_assert_multiple_comments(self.course, self.course_edit_page)

    def test_course_run_edit_page_with_multiple_comments(self):
        """ Verify course-run edit page can load multiple comments"""
        self._add_assert_multiple_comments(self.course_run, self.course_run_edit_page)

    def test_seat_edit_page_with_multiple_comments(self):
        """ Verify seat edit page can load multiple comments"""
        self._add_assert_multiple_comments(self.seat, self.seat_edit_page)

    def _add_assert_multiple_comments(self, content_object, page_path):
        """ DRY method to add comments on edit page for specific object. """
        response = self.client.get(reverse(page_path, kwargs={'pk': content_object.id}))
        self.assertContains(response, 'Total Comments 0')
        comments = []
        for num in range(1, 10):    # pylint: disable=unused-variable
            comments.append(self._generate_comment(content_object=content_object, user=self.user))

        # assert emails send
        self.assertEqual(len(mail.outbox), 9)

        response = self.client.get(reverse(page_path, kwargs={'pk': content_object.id}))
        for comment in comments:
            self.assertContains(response, comment.comment)

        self.assertContains(response, 'Total Comments 9')

    def test_comment_edit_with_course(self):
        """ Verify that only comments attached with specific course appears on edited page. """
        comments = self._generate_comments_for_all_content_types()
        response = self.client.get(reverse(self.course_edit_page, kwargs={'pk': self.course.id}))
        self.assertContains(response, comments.get(self.course).comment)
        self.assertNotContains(response, comments.get(self.course_run).comment)
        self.assertNotContains(response, comments.get(self.seat).comment)

    def test_comment_edit_with_courserun(self):
        """ Verify that only comments attached with specific course run appears on edited page. """
        comments = self._generate_comments_for_all_content_types()
        response = self.client.get(reverse(self.course_run_edit_page, kwargs={'pk': self.course_run.id}))
        self.assertContains(response, comments.get(self.course_run).comment)
        self.assertNotContains(response, comments.get(self.course).comment)
        self.assertNotContains(response, comments.get(self.seat).comment)

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

    def test_edit_course_run_comment(self):
        """ Verify that course run comment can be edited. """
        self._edit_comment_page(
            self.course_run, reverse(self.course_run_edit_page, kwargs={'pk': self.course_run.id})
        )

    def test_edit_seat_comment(self):
        """ Verify that seat comment can be edited. """
        self._edit_comment_page(
            self.seat, reverse(self.seat_edit_page, kwargs={'pk': self.seat.id})
        )

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
        # mail has 2 emails one due to newly added comment and other is due to editing.
        self.assertEqual(len(mail.outbox), 2)

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
        """ DRY method generate the comments for all available content types."""
        data = {}
        for content in [self.course, self.course_run, self.seat]:
            data[content] = self._generate_comment(content_object=content, user=self.user)

        return data

    def test_emails_without_waffle_switch(self):
        """ Verify that without enabling switch no email will be send."""
        toggle_switch('enable_emails', False)
        self._generate_comment(content_object=self.course, user=self.user)
        self.assertEqual(len(mail.outbox), 0)

    def test_emails_for_course(self):
        """ Verify that email can be send to for course."""
        comment = self._generate_comment(content_object=self.course, user=self.user)
        self.assert_comment(comment)

    def test_emails_for_course_run(self):
        """ Verify that email can be send to for course."""
        comment = self._generate_comment(content_object=self.course_run, user=self.user)
        self.assert_comment(comment)

    def test_emails_for_seat(self):
        """ Verify that email can be send to for seat."""
        comment = self._generate_comment(content_object=self.seat, user=self.user)
        self.assert_comment(comment)

    def assert_comment(self, comment):
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(str(mail.outbox[0].subject), 'New comment added.')
        self.assertEqual(mail.outbox[0].body.strip(), comment.comment)

    def _generate_users_in_group(self, number, group, enable_notification):
        """ DRY method to generate users in a group."""
        users = []
        for num in range(1, number + 1):
            user = UserFactory(
                is_staff=True, is_superuser=True, email='test-{num}@test-edx.org'.format(num=num)
            )
            self._add_attribute(user, enable_notification)
            user.groups.add(group)
            users.append(user)

        return users

    def test_emails_for_comments_multiple_users(self):
        """ Verify that email can be send to multiple users in a groups
        who has permission on object.
        """
        # add 5 users in same group
        users = self._generate_users_in_group(5, self.group, True)
        self._generate_comment(content_object=self.course, user=self.user)
        # assert emails send
        self.assertEqual(len(mail.outbox), 1)
        # assert email for receipients
        self.assertEqual(len(mail.outbox[0].to), 6)
        self.assertTrue(self.user.email in mail.outbox[0].to)
        for user in users:
            self.assertTrue(user.email in mail.outbox[0].to)

    def test_emails_for_comments_without_permission(self):
        """ Verify that emails cannot be send to those users who has no permission on
        object.
        """
        course_2 = factories.CourseFactory()
        self._generate_comment(content_object=course_2, user=self.user)
        self.assertEqual(len(mail.outbox), 0)

    def test_emails_for_comments_without_enable_notification(self):
        """ Verify that email can be send only those user who has enable the notifications."""
        self._generate_users_in_group(5, self.group, False)
        self._generate_comment(content_object=self.course, user=self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].to), 1)
