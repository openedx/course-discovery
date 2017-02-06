import json

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase

from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD


# pylint: disable=no-member
from course_discovery.apps.course_metadata.tests.factories import PositionFactory


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
        first_instructor = factories.PersonFactory(given_name="First Instructor")
        second_instructor = factories.PersonFactory(given_name="Second Instructor")
        self.instructors = [first_instructor, second_instructor]

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

    def test_instructor_autocomplete(self):
        """ Verify instructor autocomplete returns the data. """
        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins')
        )
        self._assert_response(response, 2)

        # update first instructor's name
        self.instructors[0].given_name = 'dummy_name'
        self.instructors[0].save()

        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='dummy')
        )
        self._assert_response(response, 1)

    def test_instructor_autocomplete_un_authorize_user(self):
        """ Verify instructor autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:person-autocomplete'))
        self._assert_response(response, 0)

    def test_instructor_position_in_label(self):
        """ Verify that instructor label contains position of instructor if it exists."""
        position_title = 'professor'
        PositionFactory.create(person=self.instructors[0], title=position_title, organization=self.organizations[0])

        response = self.client.get(reverse('admin_metadata:person-autocomplete'))

        self.assertContains(response, '<p>{position} at {organization}</p>'.format(
            position=position_title,
            organization=self.organizations[0].name))

    def test_instructor_image_in_label(self):
        """ Verify that instructor label contains profile image url.
        """
        response = self.client.get(reverse('admin_metadata:person-autocomplete'))
        self.assertContains(response, self.instructors[0].get_profile_image_url)
        self.assertContains(response, self.instructors[1].get_profile_image_url)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(data['results']), expected_length)
