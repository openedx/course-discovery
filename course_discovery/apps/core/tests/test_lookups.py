import json

from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory


class UserAutocompleteTests(TestCase):
    """ Tests for user autocomplete lookups."""

    def setUp(self):
        super(UserAutocompleteTests, self).setUp()
        self.user = UserFactory(username='test_name', is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.users_list = UserFactory.create_batch(5)

    def test_user_autocomplete(self):
        """ Verify user autocomplete returns the data. """
        response = self.client.get(
            reverse('admin_core:user-autocomplete') + '?q={user}'.format(user='user')
        )
        self._assert_response(response, 5)

        # update first user's username
        self.users_list[0].username = 'dummy_name'
        self.users_list[0].save()
        response = self.client.get(
            reverse('admin_core:user-autocomplete') + '?q={user}'.format(user='dummy')
        )
        self._assert_response(response, 1)

    def test_course_autocomplete_un_authorize_user(self):
        """ Verify user autocomplete returns empty list for un-authorized users. """
        self.client.logout()
        self.user.is_staff = False
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        response = self.client.get(reverse('admin_core:user-autocomplete'))
        self._assert_response(response, 0)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(data['results']), expected_length)
