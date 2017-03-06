from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher_comments.api.permissions import IsOwner
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class IsOwnerTests(TestCase):
    def setUp(self):
        super(IsOwnerTests, self).setUp()
        self.permissions_class = IsOwner()
        self.user = UserFactory.create()
        self.comment = CommentFactory.create(user=self.user, comment='test comment')

    def test_is_owner_permission(self):
        """ If object.user matches request.user, return True. """

        # users has access to their own objects
        request = self._make_request(user=self.user, data={'comment': 'update_comment'})
        self.assertTrue(self.permissions_class.has_object_permission(request, None, self.comment))

        # users CANNOT access object of other users
        user = UserFactory.create()
        request = self._make_request(user=user, data={'username': 'other_guy'})
        self.assertFalse(self.permissions_class.has_object_permission(request, None, self.comment))

    def _make_request(self, user=None, data=None):
        request = APIRequestFactory().put('/', data)

        if user:
            force_authenticate(request, user=user)

        return Request(request)
