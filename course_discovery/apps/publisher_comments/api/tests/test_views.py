import json

from django.test import TestCase
from rest_framework.reverse import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.tests import JSON_CONTENT_TYPE
from course_discovery.apps.publisher_comments.models import Comments
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class UpdateCommentTests(SiteMixin, TestCase):

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
