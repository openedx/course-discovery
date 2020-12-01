import datetime
import json
import urllib.parse

import ddt
import pytz
from django.test import TestCase
from django.urls import reverse
from rest_framework.renderers import JSONRenderer

from course_discovery.apps.api import serializers
from course_discovery.apps.api.v1.tests.test_views import mixins
from course_discovery.apps.api.v1.views.search import BrowsableAPIRendererWithoutForms, TypeaheadSearchView
from course_discovery.apps.core.tests.factories import USER_PASSWORD, PartnerFactory, UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, PersonFactory, PositionFactory, ProgramFactory
)
from course_discovery.apps.publisher.tests import factories as publisher_factories


@ddt.ddt
class CourseRunSearchViewSetTests(mixins.SerializationMixin, mixins.LoginMixin, ElasticsearchTestMixin,
                                  mixins.APITestCase):
    """ Tests for CourseRunSearchViewSet. """
    detailed_path = reverse('api:v1:search-course_runs-details')
    faceted_path = reverse('api:v1:search-course_runs-facets')
    list_path = reverse('api:v1:search-course_runs-list')

    def get_response(self, query=None, path=None):
        qs = urllib.parse.urlencode({'q': query}) if query else ''
        path = path or self.list_path
        url = f'{path}?{qs}'
        return self.client.get(url)

    def build_facet_url(self, params):
        return 'http://{domain}{path}?{query}'.format(
            domain=self.site.domain, path=self.faceted_path, query=urllib.parse.urlencode(params)
        )

    def assert_successful_search(self, path=None, serializer=None):
        """ Asserts the search functionality returns results for a generated query. """
        # Generate data that should be indexed and returned by the query
        course_run = CourseRunFactory(course__partner=self.partner, course__title='Software Testing',
                                      status=CourseRunStatus.Published)
        response = self.get_response('software', path=path)

        assert response.status_code == 200
        response_data = response.data

        # Validate the search results
        expected = {
            'count': 1,
            'results': [
                self.serialize_course_run_search(course_run, serializer=serializer)
            ]
        }
        actual = response_data['objects'] if path == self.faceted_path else response_data
        self.assertDictContainsSubset(expected, actual)

        return course_run, response_data

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

    @ddt.data(faceted_path, list_path, detailed_path)
    def test_authentication(self, path):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.get_response(path=path)
        assert response.status_code == 401

    @ddt.data(
        (list_path, serializers.CourseRunSearchSerializer,),
        (detailed_path, serializers.CourseRunSearchModelSerializer,),
    )
    @ddt.unpack
    def test_search(self, path, serializer):
        """ Verify the view returns search results. """
        self.assert_successful_search(path=path, serializer=serializer)

    def test_faceted_search(self):
        """ Verify the view returns results and facets. """
        course_run, response_data = self.assert_successful_search(path=self.faceted_path)

        # Validate the pacing facet
        expected = {
            'text': course_run.pacing_type,
            'count': 1,
        }
        self.assertDictContainsSubset(expected, response_data['fields']['pacing_type'][0])

    def test_invalid_query_facet(self):
        """ Verify the endpoint returns HTTP 400 if an invalid facet is requested. """
        facet = 'not-a-facet'
        url = f'{self.faceted_path}?selected_query_facets={facet}'

        response = self.client.get(url)
        assert response.status_code == 400

        response_data = response.json()
        expected = {'detail': f'The selected query facet [{facet}] is not valid.'}
        assert response_data == expected

    def test_availability_faceting(self):
        """ Verify the endpoint returns availability facets with the results. """
        now = datetime.datetime.now(pytz.UTC)
        archived = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2),
                                    end=now - datetime.timedelta(weeks=1), status=CourseRunStatus.Published)
        current = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2),
                                   end=now + datetime.timedelta(weeks=1), status=CourseRunStatus.Published)
        starting_soon = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(days=10),
                                         end=now + datetime.timedelta(days=90), status=CourseRunStatus.Published)
        upcoming = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(days=61),
                                    end=now + datetime.timedelta(days=90), status=CourseRunStatus.Published)

        response = self.get_response(path=self.faceted_path)
        assert response.status_code == 200
        response_data = response.json()

        # Verify all course runs are returned
        assert response_data['objects']['count'] == 4

        for run in [archived, current, starting_soon, upcoming]:
            serialized = self.serialize_course_run_search(run)
            # Force execution of lazy function.
            serialized['availability'] = serialized['availability'].strip()
            assert serialized in response_data['objects']['results']

        self.assert_response_includes_availability_facets(response_data)

        # Verify the results can be filtered based on availability
        url = '{path}?page=1&selected_query_facets={facet}'.format(
            path=self.faceted_path, facet='availability_archived'
        )
        response = self.client.get(url)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == [self.serialize_course_run_search(archived)]

    @ddt.data(
        (list_path, serializers.CourseRunSearchSerializer,
         ['results', 0, 'program_types', 0], ProgramStatus.Deleted, 5),
        (list_path, serializers.CourseRunSearchSerializer,
         ['results', 0, 'program_types', 0], ProgramStatus.Unpublished, 5),
        (detailed_path, serializers.CourseRunSearchModelSerializer,
         ['results', 0, 'programs', 0, 'type'], ProgramStatus.Deleted, 22),
        (detailed_path, serializers.CourseRunSearchModelSerializer,
         ['results', 0, 'programs', 0, 'type'], ProgramStatus.Unpublished, 23),
    )
    @ddt.unpack
    def test_exclude_unavailable_program_types(self, path, serializer, result_location_keys, program_status,
                                               expected_queries):
        """ Verify that unavailable programs do not show in the program_types representation. """
        course_run = CourseRunFactory(course__partner=self.partner, course__title='Software Testing',
                                      status=CourseRunStatus.Published)
        active_program = ProgramFactory(courses=[course_run.course], status=ProgramStatus.Active)
        ProgramFactory(courses=[course_run.course], status=program_status)
        self.reindex_courses(active_program)

        with self.assertNumQueries(expected_queries, threshold=1):  # CI sometimes adds a query
            response = self.get_response('software', path=path)
        assert response.status_code == 200
        response_data = response.data

        # Validate the search results
        expected = {
            'count': 1,
            'results': [
                self.serialize_course_run_search(course_run, serializer=serializer)
            ]
        }
        self.assertDictContainsSubset(expected, response_data)

        # Check that the program is indeed the active one.
        for key in result_location_keys:
            response_data = response_data[key]
        assert response_data == active_program.type.name

    @ddt.data(
        ([{'title': 'Software Testing', 'excluded': True}], 6),
        ([{'title': 'Software Testing', 'excluded': True}, {'title': 'Software Testing 2', 'excluded': True}], 7),
        ([{'title': 'Software Testing', 'excluded': False}, {'title': 'Software Testing 2', 'excluded': False}], 7),
        ([{'title': 'Software Testing', 'excluded': True}, {'title': 'Software Testing 2', 'excluded': True},
         {'title': 'Software Testing 3', 'excluded': False}], 5),
    )
    @ddt.unpack
    def test_excluded_course_run(self, course_runs, expected_queries):
        course_list = []
        course_run_list = []
        excluded_course_run_list = []
        non_excluded_course_run_list = []
        for run in course_runs:
            course_run = CourseRunFactory(course__partner=self.partner, course__title=run['title'],
                                          status=CourseRunStatus.Published)
            course_list.append(course_run.course)
            course_run_list.append(course_run)
            if run['excluded']:
                excluded_course_run_list.append(course_run)
            else:
                non_excluded_course_run_list.append(course_run)

        program = ProgramFactory(
            courses=course_list,
            status=ProgramStatus.Active,
            excluded_course_runs=excluded_course_run_list
        )
        self.reindex_courses(program)

        with self.assertNumQueries(expected_queries):
            response = self.get_response('software', path=self.list_path)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data['count'] == len(course_run_list)
        for result in response_data['results']:
            for course_run in excluded_course_run_list:
                if result.get('title') == course_run.title:
                    assert result.get('program_types') == []

            for course_run in non_excluded_course_run_list:
                if result.get('title') == course_run.title:
                    assert result.get('program_types') == course_run.program_types


@ddt.ddt
class AggregateSearchViewSetTests(mixins.SerializationMixin, mixins.LoginMixin, ElasticsearchTestMixin,
                                  mixins.SynonymTestMixin, mixins.APITestCase):

    def get_response(self, query=None, endpoint='api:v1:search-all-facets'):
        qs = ''

        if query:
            qs = urllib.parse.urlencode(query)

        path = reverse(endpoint)
        url = f'{path}?{qs}'
        return self.client.get(url)

    def process_response(self, response):
        response = self.get_response(response).json()
        objects = response['objects']
        assert objects['count'] > 0
        return objects

    def test_results_only_include_published_objects(self):
        """ Verify the search results only include items with status set to 'Published'. """
        # These items should NOT be in the results
        CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Unpublished)
        ProgramFactory(partner=self.partner, status=ProgramStatus.Unpublished)

        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response()
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == \
            [self.serialize_program_search(program), self.serialize_course_run_search(course_run)]

    def test_hidden_runs_excluded(self):
        """Search results should not include hidden runs."""
        visible_run = CourseRunFactory(course__partner=self.partner)
        hidden_run = CourseRunFactory(course__partner=self.partner, hidden=True)

        assert CourseRun.objects.get(hidden=True) == hidden_run

        response = self.get_response()
        data = response.json()
        assert data['objects']['results'] == [self.serialize_course_run_search(visible_run)]

    def test_non_marketable_runs_excluded(self):
        """Search results should not include non-marketable runs."""
        marketable_run = CourseRunFactory(course__partner=self.partner, type__is_marketable=True)
        CourseRunFactory(course__partner=self.partner, type__is_marketable=False)

        response = self.get_response()
        data = response.json()
        self.assertListEqual(data['objects']['results'], [self.serialize_course_run_search(marketable_run)])

    def test_results_filtered_by_default_partner(self):
        """ Verify the search results only include items related to the default partner if no partner is
        specified on the request. If a partner is included, the data should be filtered to the requested partner. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        # This data should NOT be in the results
        other_partner = PartnerFactory()
        other_course_run = CourseRunFactory(course__partner=other_partner, status=CourseRunStatus.Published)
        other_program = ProgramFactory(partner=other_partner, status=ProgramStatus.Active)
        assert other_program.partner.short_code != self.partner.short_code
        assert other_course_run.course.partner.short_code != self.partner.short_code

        response = self.get_response()
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == \
            [self.serialize_program_search(program), self.serialize_course_run_search(course_run)]

        # Filter results by partner
        response = self.get_response({'partner': other_partner.short_code})
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == \
            [self.serialize_program_search(other_program), self.serialize_course_run_search(other_course_run)]

    @ddt.data((True, 9), (False, 9))
    @ddt.unpack
    def test_query_count_exclude_expired_course_run(self, exclude_expired, expected_queries):
        """ Verify that there is no query explosion when excluding expired course runs. """
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        course_run2 = CourseRunFactory(course=course_run.course, status=CourseRunStatus.Published)
        course_run3 = CourseRunFactory(course=course_run.course, status=CourseRunStatus.Published)
        course_run4 = CourseRunFactory(course=course_run.course, status=CourseRunStatus.Published)
        self.reindex_courses(program)

        query = {'partner': self.partner.short_code}
        if exclude_expired:
            query['exclude_expired_course_run'] = 'True'

        # Filter results by partner
        with self.assertNumQueries(expected_queries):
            response = self.get_response(
                query,
                endpoint='api:v1:search-all-list'
            )
        assert response.status_code == 200
        response_data = response.json()
        expected = [
            self.serialize_course_run_search(run)
            for run in (course_run, course_run2, course_run3, course_run4)
        ] + [
            self.serialize_program_search(program),
            # We need to render the json, and then parse it again, to get all of the formatted
            # data the same as the data coming out of search.
            json.loads(JSONRenderer().render(self.serialize_course_search(course_run.course)).decode('utf-8')),
        ]
        self.assertCountEqual(response_data['results'], expected)

    def test_empty_query(self):
        """ Verify, when the query (q) parameter is empty, the endpoint behaves as if the parameter
        was not provided. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response({'q': '', 'content_type': ['courserun', 'program']})
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == \
            [self.serialize_program_search(program), self.serialize_course_run_search(course_run)]

    @ddt.data('start', '-start')
    def test_results_ordered_by_start_date(self, ordering):
        """ Verify the search results can be ordered by start date """
        now = datetime.datetime.now(pytz.UTC)
        archived = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2))
        current = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=1))
        starting_soon = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(weeks=3))
        upcoming = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(weeks=4))
        course_run_keys = [course_run.key for course_run in [archived, current, starting_soon, upcoming]]

        with self.assertNumQueries(6):
            response = self.get_response({"ordering": ordering})
        assert response.status_code == 200
        assert response.data['objects']['count'] == 4

        course_runs = CourseRun.objects.filter(key__in=course_run_keys).order_by(ordering)
        expected = [self.serialize_course_run_search(course_run) for course_run in course_runs]
        assert response.data['objects']['results'] == expected

    @ddt.data(True, False)
    def test_results_ordered_by_aggregation_key(self, ascending):
        """ Verify the search results can be ordered by start date """
        run1 = CourseRunFactory(course__partner=self.partner, course__key='edX+DemoX')
        run2 = CourseRunFactory(course__partner=self.partner, course__key='fakeX+FakeX')

        with self.assertNumQueries(6):
            response = self.get_response({'ordering': 'aggregation_key' if ascending else '-aggregation_key'})
        assert response.status_code == 200
        assert response.data['objects']['count'] == 2

        run1_data = self.serialize_course_run_search(run1)
        run2_data = self.serialize_course_run_search(run2)
        expected = [run1_data, run2_data] if ascending else [run2_data, run1_data]
        assert response.data['objects']['results'] == expected

    def test_results_include_aggregation_key(self):
        """ Verify the search results only include the aggregation_key for each document. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response()
        assert response.status_code == 200
        response_data = response.json()

        expected = sorted(
            [f'courserun:{course_run.course.key}', f'program:{program.uuid}']
        )
        actual = sorted(
            [obj.get('aggregation_key') for obj in response_data['objects']['results']]
        )
        assert expected == actual


class LimitedAggregateSearchViewSetTests(
    ElasticsearchTestMixin, mixins.LoginMixin, mixins.SerializationMixin, mixins.APITestCase
):
    path = reverse('api:v1:search-limited-facets')

    # pylint: disable=no-member
    def serialize_course_run_search(self, run):
        return super().serialize_course_run_search(run, serializers.LimitedAggregateSearchSerializer)

    # pylint: disable=no-member
    def serialize_program_search(self, program):
        return super().serialize_program_search(program, serializers.LimitedAggregateSearchSerializer)

    # pylint: disable=no-member
    def serialize_course_search(self, course):
        return super().serialize_course_search(course, serializers.LimitedAggregateSearchSerializer)

    def test_results_only_include_published_objects(self):
        """ Verify the search results only include items with status set to 'Published'. """
        # These items should NOT be in the results
        CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Unpublished)
        ProgramFactory(partner=self.partner, status=ProgramStatus.Unpublished)

        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        with self.assertNumQueries(5):
            response = self.client.get(self.path)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data['objects']['results'] == \
            [self.serialize_program_search(program), self.serialize_course_run_search(course_run)]

    def test_hidden_runs_excluded(self):
        """Search results should not include hidden runs."""
        visible_run = CourseRunFactory(course__partner=self.partner)
        hidden_run = CourseRunFactory(course__partner=self.partner, hidden=True)

        assert CourseRun.objects.get(hidden=True) == hidden_run

        with self.assertNumQueries(5):
            response = self.client.get(self.path)
        data = response.json()
        assert data['objects']['results'] == [self.serialize_course_run_search(visible_run)]

    def test_results_include_aggregation_key(self):
        """ Verify the search results only include the aggregation_key for each document. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        with self.assertNumQueries(5):
            response = self.client.get(self.path)
        assert response.status_code == 200
        response_data = response.json()

        expected = sorted(
            [f'courserun:{course_run.course.key}', f'program:{program.uuid}']
        )
        actual = sorted(
            [obj.get('aggregation_key') for obj in response_data['objects']['results']]
        )
        assert expected == actual


class AggregateCatalogSearchViewSetTests(mixins.SerializationMixin, mixins.LoginMixin, ElasticsearchTestMixin,
                                         mixins.APITestCase):
    path = reverse('api:v1:search-all-list')

    def test_post(self):
        """
        Verify that POST request works as expected for `AggregateSearchViewSet`
        """
        CourseFactory(key='course:edX+DemoX', title='ABCs of Ͳҽʂէìղց')
        data = {'content_type': 'course', 'aggregation_key': ['course:edX+DemoX']}
        expected = {'previous': None, 'results': [], 'next': None, 'count': 0}
        with self.assertNumQueries(3):
            response = self.client.post(self.path, data=data, format='json')
        assert response.json() == expected

    def test_get(self):
        """
        Verify that GET request works as expected for `AggregateSearchViewSet`
        """
        CourseFactory(key='course:edX+DemoX', title='ABCs of Ͳҽʂէìղց')
        expected = {'previous': None, 'results': [], 'next': None, 'count': 0}
        query = {'content_type': 'course', 'aggregation_key': ['course:edX+DemoX']}
        qs = urllib.parse.urlencode(query)
        url = f'{self.path}?{qs}'
        response = self.client.get(url)
        assert response.json() == expected


class BrowsableAPIRendererWithoutFormsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.method_args = ({}, {}, '', {})

    def test_get_rendered_html_form(self):
        """
        Verify that `get_rendered_html_form` returns `None`
        """
        browsable_api_renderer = BrowsableAPIRendererWithoutForms()
        assert browsable_api_renderer.get_rendered_html_form(*self.method_args) is None

    def test_get_raw_data_form(self):
        """
        Verify that `get_raw_data_form` returns `None`
        """
        browsable_api_renderer = BrowsableAPIRendererWithoutForms()
        assert browsable_api_renderer.get_raw_data_form(*self.method_args) is None


class TypeaheadSearchViewTests(mixins.TypeaheadSerializationMixin, mixins.LoginMixin, ElasticsearchTestMixin,
                               mixins.SynonymTestMixin, mixins.APITestCase):
    path = reverse('api:v1:search-typeahead')

    def get_response(self, query=None, partner=None):
        query_dict = query or {}
        query_dict.update({'partner': partner or self.partner.short_code})
        qs = urllib.parse.urlencode(query_dict)

        url = f'{self.path}?{qs}'
        return self.client.get(url)

    def process_response(self, response):
        response = self.get_response(response).json()
        self.assertTrue(response['course_runs'] or response['programs'])
        return response

    def test_typeahead(self):
        """ Test typeahead response. """
        title = "Python"
        course_run = CourseRunFactory(title=title, course__partner=self.partner)
        program = ProgramFactory(title=title, status=ProgramStatus.Active, partner=self.partner)
        response = self.get_response({'q': title})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertDictEqual(response_data, {'course_runs': [self.serialize_course_run_search(course_run)],
                                             'programs': [self.serialize_program_search(program)]})

    def test_typeahead_multiple_results(self):
        """ Verify the typeahead responses always returns a limited number of results, even if there are more hits. """
        RESULT_COUNT = TypeaheadSearchView.RESULT_COUNT
        title = "Test"
        for i in range(RESULT_COUNT + 1):
            CourseRunFactory(title=f"{title}{i}", course__partner=self.partner)
            ProgramFactory(title=f"{title}{i}", status=ProgramStatus.Active, partner=self.partner)
        response = self.get_response({'q': title})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(len(response_data['course_runs']), RESULT_COUNT)
        self.assertEqual(len(response_data['programs']), RESULT_COUNT)

    def test_typeahead_deduplicate_course_runs(self):
        """ Verify the typeahead response will only include the first course run per course. """
        RESULT_COUNT = TypeaheadSearchView.RESULT_COUNT
        title = "Test"
        course1 = CourseFactory(partner=self.partner)
        course2 = CourseFactory(partner=self.partner)
        for i in range(RESULT_COUNT):
            CourseRunFactory(title=f"{title}{course1.title}{i}", course=course1)
        for i in range(RESULT_COUNT):
            CourseRunFactory(title=f"{title}{course2.title}{i}", course=course2)
        response = self.get_response({'q': title})
        assert response.status_code == 200
        response_data = response.json()

        # There are many runs for both courses, but only one from each will be included
        course_runs = response_data['course_runs']
        assert len(course_runs) == 2
        # compare course titles embedded in course run title to ensure that course runs belong to different courses
        assert course_runs[0]['title'][4:-1] != course_runs[1]['title'][4:-1]

    def test_typeahead_multiple_authoring_organizations(self):
        """ Test typeahead response with multiple authoring organizations. """
        title = "Design"
        authoring_organizations = OrganizationFactory.create_batch(3)
        course_run = CourseRunFactory(
            title=title,
            authoring_organizations=authoring_organizations,
            course__partner=self.partner
        )
        program = ProgramFactory(
            title=title, authoring_organizations=authoring_organizations,
            status=ProgramStatus.Active, partner=self.partner
        )
        response = self.get_response({'q': title})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertDictEqual(response_data, {'course_runs': [self.serialize_course_run_search(course_run)],
                                             'programs': [self.serialize_program_search(program)]})

    def test_partial_term_search(self):
        """ Test typeahead response with partial term search. """
        title = "Learn Data Science"
        course_run = CourseRunFactory(title=title, course__partner=self.partner)
        program = ProgramFactory(title=title, status=ProgramStatus.Active, partner=self.partner)
        query = "Data Sci"
        response = self.get_response({'q': query})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        expected_response_data = {
            'course_runs': [self.serialize_course_run_search(course_run)],
            'programs': [self.serialize_program_search(program)]
        }
        self.assertDictEqual(response_data, expected_response_data)

    def test_unpublished_and_hidden_courses(self):
        """ Verify that typeahead does not return unpublished or hidden courses
        or programs that are not active. """
        title = "supply"
        course_run = CourseRunFactory(title=title, course__partner=self.partner)
        CourseRunFactory(title=title + "unpublished", status=CourseRunStatus.Unpublished, course__partner=self.partner)
        CourseRunFactory(title=title + "hidden", hidden=True, course__partner=self.partner)
        program = ProgramFactory(title=title, status=ProgramStatus.Active, partner=self.partner)
        ProgramFactory(title=title + "unpublished", status=ProgramStatus.Unpublished, partner=self.partner)
        query = "suppl"
        response = self.get_response({'q': query})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        expected_response_data = {
            'course_runs': [self.serialize_course_run_search(course_run)],
            'programs': [self.serialize_program_search(program)]
        }
        self.assertDictEqual(response_data, expected_response_data)

    def test_typeahead_hidden_programs(self):
        """ Verify that typeahead does not return hidden programs. """
        title = "hiddenprogram"
        program = ProgramFactory(title=title, hidden=False, status=ProgramStatus.Active, partner=self.partner)
        ProgramFactory(title=program.title + 'hidden', hidden=True, status=ProgramStatus.Active, partner=self.partner)
        response = self.get_response({'q': program.title})
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        expected_response_data = {
            'course_runs': [],
            'programs': [self.serialize_program_search(program)]
        }
        self.assertDictEqual(response_data, expected_response_data)

    def test_exception(self):
        """ Verify the view raises an error if the 'q' query string parameter is not provided. """
        response = self.get_response()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, ["The 'q' querystring parameter is required for searching."])

    def test_typeahead_authoring_organizations_partial_search(self):
        """ Test typeahead response with partial organization matching. """
        authoring_organizations = OrganizationFactory.create_batch(3)
        course_run = CourseRunFactory.create(course__partner=self.partner)
        program = ProgramFactory.create(partner=self.partner)
        for authoring_organization in authoring_organizations:
            course_run.authoring_organizations.add(authoring_organization)
            program.authoring_organizations.add(authoring_organization)
        course_run.save()
        program.save()
        partial_key = authoring_organizations[0].key[0:5]

        response = self.get_response({'q': partial_key})
        self.assertEqual(response.status_code, 200)

        # This call is flaky in CI. It is reliable locally, but occasionally in our CI environment,
        # this call won't contain the data for course_runs and programs. Instead of relying on the factories
        # we now explicitly add the authoring organizations to a course_run and program and call .save()
        # in order to update the search indexes.
        expected = {
            'course_runs': [self.serialize_course_run_search(course_run)],
            'programs': [self.serialize_program_search(program)]
        }
        self.assertDictEqual(response.data, expected)

    def test_typeahead_org_course_runs_come_up_first(self):
        """ Test typeahead response to ensure org is taken into account. """
        MITx = OrganizationFactory(key='MITx')
        HarvardX = OrganizationFactory(key='HarvardX')
        mit_run = CourseRunFactory(
            authoring_organizations=[MITx, HarvardX],
            title='MIT Testing1',
            course__partner=self.partner
        )
        harvard_run = CourseRunFactory(
            authoring_organizations=[HarvardX],
            title='MIT Testing2',
            course__partner=self.partner
        )
        mit_program = ProgramFactory(
            authoring_organizations=[MITx, HarvardX],
            title='MIT Testing1',
            partner=self.partner
        )
        harvard_program = ProgramFactory(
            authoring_organizations=[HarvardX],
            title='MIT Testing2',
            partner=self.partner
        )
        response = self.get_response({'q': 'mit'})
        self.assertEqual(response.status_code, 200)
        expected = {
            'course_runs': [self.serialize_course_run_search(mit_run),
                            self.serialize_course_run_search(harvard_run)],
            'programs': [self.serialize_program_search(mit_program),
                         self.serialize_program_search(harvard_program)]
        }
        self.assertDictEqual(response.data, expected)


class TestPersonFacetSearchViewSet(mixins.SerializationMixin, mixins.LoginMixin,
                                   ElasticsearchTestMixin, mixins.APITestCase):
    path = reverse('api:v1:search-people-facets')

    def test_search_single(self):
        org = OrganizationFactory()
        course = CourseFactory(authoring_organizations=[org])
        person1 = PersonFactory(partner=self.partner)
        person2 = PersonFactory(partner=self.partner)
        PersonFactory(partner=self.partner)
        CourseRunFactory(staff=[person1, person2], course=course)

        facet_name = f'organizations_exact:{org.key}'
        self.reindex_people(person1)
        self.reindex_people(person2)

        query = {'selected_facets': facet_name}
        qs = urllib.parse.urlencode(query)
        url = f'{self.path}?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['objects']['count'], 2)

        query = {'selected_facets': facet_name, 'q': person1.uuid}
        qs = urllib.parse.urlencode(query)
        url = f'{self.path}?{qs}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['objects']['count'], 1)
        self.assertEqual(response_data['objects']['results'][0]['uuid'], str(person1.uuid))
        self.assertEqual(response_data['objects']['results'][0]['full_name'], person1.full_name)


class AutoCompletePersonTests(mixins.APITestCase):
    """
    Tests for person autocomplete lookups
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        first_instructor = PersonFactory(given_name="First", family_name="Instructor")
        second_instructor = PersonFactory(given_name="Second", family_name="Instructor")
        self.instructors = [first_instructor, second_instructor]

        self.organizations = OrganizationFactory.create_batch(3)
        self.organization_extensions = []

        for instructor in self.instructors:
            PositionFactory(organization=self.organizations[0], title="professor", person=instructor)

        for organization in self.organizations:
            org_ex = publisher_factories.OrganizationExtensionFactory(organization=organization)
            self.organization_extensions.append(org_ex)

        disco_course = CourseFactory(authoring_organizations=[self.organizations[0]])
        disco_course2 = CourseFactory(authoring_organizations=[self.organizations[1]])
        CourseRunFactory(course=disco_course, staff=[first_instructor])
        CourseRunFactory(course=disco_course2, staff=[second_instructor])

        self.user.groups.add(self.organization_extensions[0].group)

    def query(self, q):
        query_params = f'?q={q}'
        path = reverse('api:v1:person-search-typeahead')
        return self.client.get(path + query_params)

    def test_instructor_autocomplete(self):
        """ Verify instructor autocomplete returns the data. """
        response = self.query('ins')
        self._assert_response(response, 2)

        # update first instructor's name
        self.instructors[0].given_name = 'dummy_name'
        self.instructors[0].save()

        response = self.query('dummy')
        self._assert_response(response, 1)

    def test_instructor_autocomplete_non_staff_user(self):
        """ Verify instructor autocomplete works for non-staff users. """
        self._make_user_non_staff()
        response = self.query('dummy')
        self._assert_response(response, 0)

    def test_instructor_autocomplete_no_query_param(self):
        """ Verify instructor autocomplete returns bad response for request with no query. """
        self._make_user_non_staff()
        response = self.client.get(reverse('api:v1:person-search-typeahead'))
        self._assert_error_response(response, ["The 'q' querystring parameter is required for searching."], 400)

    def test_instructor_autocomplete_spaces(self):
        """ Verify instructor autocomplete allows spaces. """
        response = self.query('sec ins')
        self._assert_response(response, 1)

    def test_instructor_autocomplete_no_results(self):
        """ Verify instructor autocomplete correctly finds no matches if string doesn't match. """
        response = self.query('second nope')
        self._assert_response(response, 0)

    def test_instructor_autocomplete_last_name_first_name(self):
        """ Verify instructor autocomplete allows last name first. """
        response = self.query('instructor first')
        self._assert_response(response, 1)

    def test_instructor_position_in_label(self):
        """ Verify that instructor label contains position of instructor if it exists."""
        position_title = 'professor'

        response = self.query('ins')

        self.assertContains(response, position_title)

    def test_instructor_image_in_label(self):
        """ Verify that instructor label contains profile image url."""
        response = self.query('ins')
        self.assertContains(response, self.instructors[0].get_profile_image_url)
        self.assertContains(response, self.instructors[1].get_profile_image_url)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        assert response.status_code == 200
        data = json.loads(response.content.decode('utf-8'))
        assert len(data) == expected_length

    def _assert_error_response(self, response, expected_response, expected_response_code=200):
        """ Assert autocomplete response. """
        assert response.status_code == expected_response_code
        data = json.loads(response.content.decode('utf-8'))
        assert data == expected_response

    def test_instructor_autocomplete_with_uuid(self):
        """ Verify instructor autocomplete returns the data with valid uuid. """
        uuid = self.instructors[0].uuid
        response = self.query(uuid)
        self._assert_response(response, 1)

    def test_instructor_autocomplete_with_invalid_uuid(self):
        """ Verify instructor autocomplete returns empty list without giving error. """
        uuid = 'invalid-uuid'
        response = self.query(uuid)
        self._assert_response(response, 0)

    def test_instructor_autocomplete_without_staff_user(self):
        """ Verify instructor autocomplete returns the data if user is not staff. """
        non_staff_user = UserFactory()
        non_staff_user.groups.add(self.organization_extensions[0].group)
        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        response = self.query('ins')
        self._assert_response(response, 2)

    def test_instructor_autocomplete_without_login(self):
        """ Verify instructor autocomplete returns a forbidden code if user is not logged in. """
        self.client.logout()
        person_autocomplete_url = reverse(
            'api:v1:person-search-typeahead'
        ) + '?q={q}'.format(q=self.instructors[0].uuid)

        response = self.client.get(person_autocomplete_url)
        self._assert_error_response(response, {'detail': 'Authentication credentials were not provided.'}, 401)

    def test_autocomplete_limit_by_org(self):
        org = self.organizations[0]
        person_autocomplete_url = reverse(
            'api:v1:person-search-typeahead'
        ) + '?q=ins'
        single_autocomplete_url = person_autocomplete_url + f'&org={org.key}'
        response = self.client.get(single_autocomplete_url)
        self._assert_response(response, 1)

        org2 = self.organizations[1]
        multiple_autocomplete_url = single_autocomplete_url + f'&org={org2.key}'
        response = self.client.get(multiple_autocomplete_url)
        self._assert_response(response, 2)

    def _make_user_non_staff(self):
        self.client.logout()
        self.user = UserFactory(is_staff=False)
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
