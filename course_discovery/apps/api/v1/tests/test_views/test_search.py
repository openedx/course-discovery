import datetime
import json
import urllib.parse

import ddt
from django.conf import settings
from django.core.urlresolvers import reverse
from haystack.query import SearchQuerySet
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import CourseRunSearchSerializer, ProgramSearchSerializer
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD, PartnerFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory


class SerializationMixin:
    def serialize_course_run(self, course_run):
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        return CourseRunSearchSerializer(result).data

    def serialize_program(self, program):
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        return ProgramSearchSerializer(result).data


class LoginMixin:
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)


class DefaultPartnerMixin:
    def setUp(self):
        super(DefaultPartnerMixin, self).setUp()
        self.partner = PartnerFactory(pk=settings.DEFAULT_PARTNER_ID)


@ddt.ddt
class CourseRunSearchViewSetTests(DefaultPartnerMixin, SerializationMixin, LoginMixin, ElasticsearchTestMixin,
                                  APITestCase):
    """ Tests for CourseRunSearchViewSet. """
    faceted_path = reverse('api:v1:search-course_runs-facets')
    list_path = reverse('api:v1:search-course_runs-list')

    def get_search_response(self, query=None, faceted=False):
        qs = ''

        if query:
            qs = urllib.parse.urlencode({'q': query})

        path = self.faceted_path if faceted else self.list_path
        url = '{path}?{qs}'.format(path=path, qs=qs)
        return self.client.get(url)

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
        course_run = CourseRunFactory(course__partner=self.partner, course__title='Software Testing',
                                      status=CourseRunStatus.Published)
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

    def build_facet_url(self, params):
        return 'http://testserver{path}?{query}'.format(path=self.faceted_path, query=urllib.parse.urlencode(params))

    def test_invalid_query_facet(self):
        """ Verify the endpoint returns HTTP 400 if an invalid facet is requested. """
        facet = 'not-a-facet'
        url = '{path}?selected_query_facets={facet}'.format(path=self.faceted_path, facet=facet)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content.decode('utf-8'))
        expected = {'detail': 'The selected query facet [{facet}] is not valid.'.format(facet=facet)}
        self.assertEqual(response_data, expected)

    def test_availability_faceting(self):
        """ Verify the endpoint returns availability facets with the results. """
        now = datetime.datetime.utcnow()
        archived = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2),
                                    end=now - datetime.timedelta(weeks=1), status=CourseRunStatus.Published)
        current = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2),
                                   end=now + datetime.timedelta(weeks=1), status=CourseRunStatus.Published)
        starting_soon = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(days=10),
                                         end=now + datetime.timedelta(days=90), status=CourseRunStatus.Published)
        upcoming = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(days=61),
                                    end=now + datetime.timedelta(days=90), status=CourseRunStatus.Published)

        response = self.get_search_response(faceted=True)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        # Verify all course runs are returned
        self.assertEqual(response_data['objects']['count'], 4)
        expected = [self.serialize_course_run(course_run) for course_run in
                    [archived, current, starting_soon, upcoming]]
        self.assertEqual(response_data['objects']['results'], expected)

        self.assert_response_includes_availability_facets(response_data)

        # Verify the results can be filtered based on availability
        url = '{path}?page=1&selected_query_facets={facet}'.format(
            path=self.faceted_path, facet='availability_archived'
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['objects']['results'], [self.serialize_course_run(archived)])

    def assert_response_includes_availability_facets(self, response_data):
        """ Verifies the query facet counts/URLs are properly rendered. """
        expected = {
            'availability_archived': {
                'count': 1,
                'narrow_url': self.build_facet_url({'selected_query_facets': 'availability_archived'})
            },
            'availability_current': {
                'count': 1,
                'narrow_url': self.build_facet_url({'selected_query_facets': 'availability_current'})
            },
            'availability_starting_soon': {
                'count': 1,
                'narrow_url': self.build_facet_url({'selected_query_facets': 'availability_starting_soon'})
            },
            'availability_upcoming': {
                'count': 1,
                'narrow_url': self.build_facet_url({'selected_query_facets': 'availability_upcoming'})
            },
        }
        self.assertDictContainsSubset(expected, response_data['queries'])


class AggregateSearchViewSet(DefaultPartnerMixin, SerializationMixin, LoginMixin, ElasticsearchTestMixin, APITestCase):
    path = reverse('api:v1:search-all-facets')

    def get_search_response(self, querystring=None):
        querystring = querystring or {}
        qs = urllib.parse.urlencode(querystring)

        url = '{path}?{qs}'.format(path=self.path, qs=qs)
        return self.client.get(url)

    def test_results_only_include_published_objects(self):
        """ Verify the search results only include items with status set to 'Published'. """
        # These items should NOT be in the results
        CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Unpublished)
        ProgramFactory(partner=self.partner, status=ProgramStatus.Unpublished)

        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_search_response()
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_course_run(course_run), self.serialize_program(program)])

    def test_hidden_runs_excluded(self):
        """Search results should not include hidden runs."""
        visible_run = CourseRunFactory(course__partner=self.partner)
        hidden_run = CourseRunFactory(course__partner=self.partner, hidden=True)

        self.assertEqual(CourseRun.objects.get(hidden=True), hidden_run)

        response = self.get_search_response()
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            data['objects']['results'],
            [self.serialize_course_run(visible_run)]
        )

    def test_results_filtered_by_default_partner(self):
        """ Verify the search results only include items related to the default partner if no partner is
        specified on the request. If a partner is included, the data should be filtered to the requested partner. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        # This data should NOT be in the results
        other_partner = PartnerFactory()
        other_course_run = CourseRunFactory(course__partner=other_partner, status=CourseRunStatus.Published)
        other_program = ProgramFactory(partner=other_partner, status=ProgramStatus.Active)
        self.assertNotEqual(other_program.partner.short_code, self.partner.short_code)
        self.assertNotEqual(other_course_run.course.partner.short_code, self.partner.short_code)

        response = self.get_search_response()
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_program(program), self.serialize_course_run(course_run)])

        # Filter results by partner
        response = self.get_search_response({'partner': other_partner.short_code})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_course_run(other_course_run), self.serialize_program(other_program)])

    def test_empty_query(self):
        """ Verify, when the query (q) parameter is empty, the endpoint behaves as if the parameter
        was not provided. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_search_response({'q': '', 'content_type': ['courserun', 'program']})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_course_run(course_run), self.serialize_program(program)])
