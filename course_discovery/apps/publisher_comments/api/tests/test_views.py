import json

from django.test import TestCase
from rest_framework.reverse import reverse

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.tests import JSON_CONTENT_TYPE
from course_discovery.apps.publisher.tests.factories import CourseRunFactory
from course_discovery.apps.publisher_comments.forms import CommentsForm
from course_discovery.apps.publisher_comments.models import Comments
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class PostCommentTests(TestCase):

    def generate_data(self, obj):
        """Generate data for the form."""
        f = CommentsForm(obj)
        data = {
            'name': 'Tester',
            'email': 'tester@example.com',
            'comment': 'Test comment'
        }
        data.update(f.initial)
        return data

    def test_successful_post(self):
        """Posting data to the comment post endpoint creates a comment."""
        path = reverse('comments-post-comment')
        self.assertEqual(Comments.objects.count(), 0)
        course_run = CourseRunFactory()
        generated_data = self.generate_data(course_run)
        self.client.post(path, data=generated_data)

        self.assertEqual(Comments.objects.count(), 1)
        comment = Comments.objects.first()
        self.assertEqual(comment.user_name, generated_data['name'])
        self.assertEqual(comment.comment, generated_data['comment'])
        self.assertEqual(comment.user_email, generated_data['email'])


class UpdateCommentTests(TestCase):

    def setUp(self):
        super(UpdateCommentTests, self).setUp()

        self.user = UserFactory.create()
        self.comment = CommentFactory.create(user=self.user)
        self.path = reverse('publisher_comments:api:comments', kwargs={'pk': self.comment.id})
        self.data = {'comment': 'updated comment'}

    def test_update(self):
        """ Verify update endpoint allows to update 'comment'. """

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        response = self.client.patch(self.path, json.dumps(self.data), JSON_CONTENT_TYPE)

        comment = Comments.objects.get(id=self.comment.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(comment.comment, self.data['comment'])

    def test_update_without_editing_permission(self):
        """ Verify that non owner user of the comment can not edit. """
        dummy_user = UserFactory.create()
        self.client.login(username=dummy_user.username, password=USER_PASSWORD)

        response = self.client.patch(self.path, json.dumps(self.data), JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 403)
