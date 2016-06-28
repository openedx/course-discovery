import json
import urllib.parse

import ddt
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory


@ddt.ddt
class CourseRunSearchViewSetTests(ElasticsearchTestMixin, APITestCase):
    """ Tests for CourseRunSearchViewSet. """
    faceted_path = reverse('api:v1:search-course_runs-facets')
    list_path = reverse('api:v1:search-course_runs-list')

    def setUp(self):
        super(CourseRunSearchViewSetTests, self).setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def get_search_response(self, query=None, faceted=False):
        qs = ''

        if query:
            qs = urllib.parse.urlencode({'q': query})

        path = self.faceted_path if faceted else self.list_path
        url = '{path}?{qs}'.format(path=path, qs=qs)
        return self.client.get(url)

    def serialize_date(self, d):
        return d.strftime('%Y-%m-%dT%H:%M:%S') if d else None

    def serialize_language(self, language):
        return language.name

    def serialize_course_run(self, course_run):
        return {
            'transcript_languages': [self.serialize_language(l) for l in course_run.transcript_languages.all()],
            'short_description': course_run.short_description,
            'start': self.serialize_date(course_run.start),
            'end': self.serialize_date(course_run.end),
            'enrollment_start': self.serialize_date(course_run.enrollment_start),
            'enrollment_end': self.serialize_date(course_run.enrollment_end),
            'key': course_run.key,
            'marketing_url': course_run.marketing_url,
            'pacing_type': course_run.pacing_type,
            'language': self.serialize_language(course_run.language),
            'full_description': course_run.full_description,
            'title': course_run.title,
            'content_type': 'courserun'
        }

    @ddt.data(True, False)
    def test_authentication(self, faceted):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.get_search_response(faceted=faceted)
        self.assertEqual(response.status_code, 403)

    def test_search(self):
        """ Verify the view returns search results. """
        self.assert_successful_search(faceted=False)

    def test_faceted_search(self):
        """ Verify the view returns results and facets. """
        course_run, response_data = self.assert_successful_search(faceted=True)

        # Validate the pacing facet
        expected = {
            'text': course_run.pacing_type,
            'count': 1,
        }
        self.assertDictContainsSubset(expected, response_data['fields']['pacing_type'][0])

    def assert_successful_search(self, faceted=False):
        """ Asserts the search functionality returns results for a generated query. """

        # Generate data that should be indexed and returned by the query
        course_run = CourseRunFactory(course__title='Software Testing')
        response = self.get_search_response('software', faceted=faceted)

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        # Validate the search results
        expected = {
            'count': 1,
            'results': [
                self.serialize_course_run(course_run)
            ]
        }
        actual = response_data['objects'] if faceted else response_data
        self.assertDictContainsSubset(expected, actual)

        return course_run, response_data
