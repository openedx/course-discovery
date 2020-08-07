import json

import ddt
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=no-member
@ddt.ddt
class AutocompleteTests(SiteMixin, TestCase):
    """ Tests for autocomplete lookups."""
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.language_tag_test = LanguageTag.objects.create(code='xx-xx', name='Test LanguageTag')

    @ddt.data('xx', 'languagetag')
    def test_language_tag_autocomplete(self, query):
        """ Verify course autocomplete returns the queried data. """
        response = self.client.get(
            reverse('language_tags:language-tag-autocomplete') + f'?q={query}'
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'][0]['text'], str(self.language_tag_test))

    def test_language_tag_autocomplete_no_query(self):
        """ Verify course autocomplete returns all the data. """
        response = self.client.get(reverse('language_tags:language-tag-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        # Lookup returns top 10 results by default
        self.assertEqual(len(data['results']), 10)

    def test_language_tag_autocomplete_no_data(self):
        """ Verify course autocomplete returns the data. """
        response = self.client.get(
            reverse('language_tags:language-tag-autocomplete') + '?q={query}'.format(query='no results query')
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 0)
