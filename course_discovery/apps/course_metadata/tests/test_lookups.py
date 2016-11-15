import json

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase

from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD


# pylint: disable=no-member
@ddt.ddt
class AutocompleteTests(TestCase):
    """ Tests for autocomplete lookups."""
    def setUp(self):
        super(AutocompleteTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.courses = factories.CourseFactory.create_batch(3, title='Some random course title')
        for course in self.courses:
            factories.CourseRunFactory(course=course)
        self.organizations = factories.OrganizationFactory.create_batch(3)

    @ddt.data('dum', 'ing')
    def test_course_autocomplete(self, search_key):
        """ Verify course autocomplete returns the data. """
        response = self.client.get(reverse('admin_metadata:course-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 3)
        # update the first course title
        self.courses[0].key = 'edx/dummy/key'
        self.courses[0].title = 'this is some thing new'
        self.courses[0].save()
        response = self.client.get(
            reverse('admin_metadata:course-autocomplete') + '?q={title}'.format(title=search_key)
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'][0]['text'], str(self.courses[0]))

    def test_course_autocomplete_un_authorize_user(self):
        """ Verify course autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:course-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'], [])

    @ddt.data('ing', 'dum')
    def test_course_run_autocomplete(self, search_key):
        """ Verify course run autocomplete returns the data. """
        response = self.client.get(reverse('admin_metadata:course-run-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 3)
        # update the first course title
        course = self.courses[0]
        course.title = 'this is some thing new'
        course.save()
        course_run = self.courses[0].course_runs.first()
        course_run.key = 'edx/dummy/testrun'
        course_run.save()

        response = self.client.get(
            reverse('admin_metadata:course-run-autocomplete') + '?q={q}'.format(q=search_key)
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'][0]['text'], str(course_run))

    def test_course_run_autocomplete_un_authorize_user(self):
        """ Verify course run autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:course-run-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'], [])

    @ddt.data('irc', 'ing')
    def test_organization_autocomplete(self, search_key):
        """ Verify Organization autocomplete returns the data. """
        response = self.client.get(reverse('admin_metadata:organisation-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 3)

        self.organizations[0].key = 'Mirco'
        self.organizations[0].name = 'testing name'
        self.organizations[0].save()

        response = self.client.get(
            reverse('admin_metadata:organisation-autocomplete') + '?q={key}'.format(
                key=search_key
            )
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'][0]['text'], str(self.organizations[0]))
        self.assertEqual(len(data['results']), 1)

    def test_organization_autocomplete_un_authorize_user(self):
        """ Verify Organization autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:organisation-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'], [])

    @ddt.data('dummyurl', 'testing')
    def test_video_autocomplete(self, search_key):
        """ Verify video autocomplete returns the data. """
        response = self.client.get(reverse('admin_metadata:video-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['results']), 6)

        self.courses[0].video.src = 'http://www.youtube.com/dummyurl'
        self.courses[0].video.description = 'testing description'
        self.courses[0].video.save()

        response = self.client.get(
            reverse('admin_metadata:video-autocomplete') + '?q={key}'.format(
                key=search_key
            )
        )
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'][0]['text'], str(self.courses[0].video))
        self.assertEqual(len(data['results']), 1)

    def test_video_autocomplete_un_authorize_user(self):
        """ Verify video autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:video-autocomplete'))
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['results'], [])

    def _make_user_non_staff(self):
        self.client.logout()
        self.user = UserFactory(is_staff=False)
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
