import datetime
import json
import urllib.parse

import ddt
from django.conf import settings
from django.urls import reverse
from haystack.query import SearchQuerySet
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import (CourseRunSearchSerializer, ProgramSearchSerializer,
                                                   TypeaheadCourseRunSearchSerializer, TypeaheadProgramSearchSerializer)
from course_discovery.apps.api.v1.views.search import TypeaheadSearchView
from course_discovery.apps.core.tests.factories import USER_PASSWORD, PartnerFactory, UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import (CourseFactory, CourseRunFactory, OrganizationFactory,
                                                                   ProgramFactory)


class SerializationMixin:
    def serialize_course_run(self, course_run):
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        return CourseRunSearchSerializer(result).data

    def serialize_program(self, program):
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        return ProgramSearchSerializer(result).data


class TypeaheadSerializationMixin:
    def serialize_course_run(self, course_run):
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        data = TypeaheadCourseRunSearchSerializer(result).data
        return data

    def serialize_program(self, program):
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        data = TypeaheadProgramSearchSerializer(result).data
        return data


class LoginMixin:
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)


class SynonymTestMixin:

    def test_org_synonyms(self):
        """ Test that synonyms work for organization names """
        title = 'UniversityX'
        authoring_organizations = [OrganizationFactory(name='University')]
        CourseRunFactory(
            title=title,
            course__partner=self.partner,
            authoring_organizations=authoring_organizations
        )
        ProgramFactory(title=title, partner=self.partner, authoring_organizations=authoring_organizations)
        response1 = self.process_response({'q': title})
        response2 = self.process_response({'q': 'University'})
        self.assertDictEqual(response1, response2)

    def test_title_synonyms(self):
        """ Test that synonyms work for terms in the title """
        CourseRunFactory(title='HTML', course__partner=self.partner)
        ProgramFactory(title='HTML', partner=self.partner)
        response1 = self.process_response({'q': 'HTML5'})
        response2 = self.process_response({'q': 'HTML'})
        self.assertDictEqual(response1, response2)

    def test_special_character_synonyms(self):
        """ Test that synonyms work with special characters (non ascii) """
        ProgramFactory(title='spanish', partner=self.partner)
        response1 = self.process_response({'q': 'spanish'})
        response2 = self.process_response({'q': 'español'})
        self.assertDictEqual(response1, response2)

    def test_stemmed_synonyms(self):
        """ Test that synonyms work with stemming from the snowball analyzer """
        title = 'Running'
        ProgramFactory(title=title, partner=self.partner)
        response1 = self.process_response({'q': 'running'})
        response2 = self.process_response({'q': 'jogging'})
        self.assertDictEqual(response1, response2)


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

    def get_response(self, query=None, faceted=False):
        qs = ''

        if query:
            qs = urllib.parse.urlencode({'q': query})

        path = self.faceted_path if faceted else self.list_path
        url = '{path}?{qs}'.format(path=path, qs=qs)
        return self.client.get(url)

    def process_response(self, response):
        response = self.get_response(response).json()
        self.assertTrue(response['objects']['count'])
        return response['objects']

    @ddt.data(True, False)
    def test_authentication(self, faceted):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.get_response(faceted=faceted)
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
        response = self.get_response('software', faceted=faceted)

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

        response = self.get_response(faceted=True)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        # Verify all course runs are returned
        self.assertEqual(response_data['objects']['count'], 4)

        for run in [archived, current, starting_soon, upcoming]:
            serialized = self.serialize_course_run(run)
            # Force execution of lazy function.
            serialized['availability'] = serialized['availability'].strip()
            self.assertIn(serialized, response_data['objects']['results'])

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

    def test_exclude_deleted_program_types(self):
        """ Verify the deleted programs do not show in the program_types representation. """
        self._test_exclude_program_types(ProgramStatus.Deleted)

    def test_exclude_unpublished_program_types(self):
        """ Verify the unpublished programs do not show in the program_types representation. """
        self._test_exclude_program_types(ProgramStatus.Unpublished)

    @ddt.data(
        [{'title': 'Software Testing', 'excluded': True}],
        [{'title': 'Software Testing', 'excluded': True}, {'title': 'Software Testing 2', 'excluded': True}],
        [{'title': 'Software Testing', 'excluded': False}, {'title': 'Software Testing 2', 'excluded': False}],
        [{'title': 'Software Testing', 'excluded': True}, {'title': 'Software Testing 2', 'excluded': True},
         {'title': 'Software Testing 3', 'excluded': False}],
    )
    def test_excluded_course_run(self, course_runs):
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

        with self.assertNumQueries(4):
            response = self.get_response('software', faceted=False)

        self.assertEqual(response.status_code, 200)
        response_data = response.json()

        self.assertEqual(response_data['count'], len(course_run_list))
        for result in response_data['results']:
            for course_run in excluded_course_run_list:
                if result.get('title') == course_run.title:
                    self.assertEqual(result.get('program_types'), [])

            for course_run in non_excluded_course_run_list:
                if result.get('title') == course_run.title:
                    self.assertEqual(result.get('program_types'), course_run.program_types)

    def _test_exclude_program_types(self, program_status):
        """ Verify that programs with the provided type do not show in the program_types representation. """
        course_run = CourseRunFactory(course__partner=self.partner, course__title='Software Testing',
                                      status=CourseRunStatus.Published)
        active_program = ProgramFactory(courses=[course_run.course], status=ProgramStatus.Active)
        ProgramFactory(courses=[course_run.course], status=program_status)
        self.reindex_courses(active_program)

        with self.assertNumQueries(5):
            response = self.get_response('software', faceted=False)

            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content.decode('utf-8'))

            # Validate the search results
            expected = {
                'count': 1,
                'results': [
                    self.serialize_course_run(course_run)
                ]
            }
            self.assertDictContainsSubset(expected, response_data)
            self.assertEqual(response_data['results'][0].get('program_types'), [active_program.type.name])


@ddt.ddt
class AggregateSearchViewSetTests(DefaultPartnerMixin, SerializationMixin, LoginMixin, ElasticsearchTestMixin,
                                  SynonymTestMixin, APITestCase):
    path = reverse('api:v1:search-all-facets')

    def get_response(self, query=None):
        qs = ''

        if query:
            qs = urllib.parse.urlencode(query)

        url = '{path}?{qs}'.format(path=self.path, qs=qs)
        return self.client.get(url)

    def process_response(self, response):
        response = self.get_response(response).json()
        self.assertTrue(response['objects']['count'])
        return response['objects']

    def test_results_only_include_published_objects(self):
        """ Verify the search results only include items with status set to 'Published'. """
        # These items should NOT be in the results
        CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Unpublished)
        ProgramFactory(partner=self.partner, status=ProgramStatus.Unpublished)

        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response()
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(
            response_data['objects']['results'],
            [self.serialize_program(program), self.serialize_course_run(course_run)]
        )

    def test_hidden_runs_excluded(self):
        """Search results should not include hidden runs."""
        visible_run = CourseRunFactory(course__partner=self.partner)
        hidden_run = CourseRunFactory(course__partner=self.partner, hidden=True)

        self.assertEqual(CourseRun.objects.get(hidden=True), hidden_run)

        response = self.get_response()
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

        response = self.get_response()
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(
            response_data['objects']['results'],
            [self.serialize_program(program), self.serialize_course_run(course_run)]
        )

        # Filter results by partner
        response = self.get_response({'partner': other_partner.short_code})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_program(other_program), self.serialize_course_run(other_course_run)])

    def test_empty_query(self):
        """ Verify, when the query (q) parameter is empty, the endpoint behaves as if the parameter
        was not provided. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response({'q': '', 'content_type': ['courserun', 'program']})
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertListEqual(response_data['objects']['results'],
                             [self.serialize_program(program), self.serialize_course_run(course_run)])

    @ddt.data('start', '-start')
    def test_results_ordered_by_start_date(self, ordering):
        """ Verify the search results can be ordered by start date """
        now = datetime.datetime.utcnow()
        archived = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=2))
        current = CourseRunFactory(course__partner=self.partner, start=now - datetime.timedelta(weeks=1))
        starting_soon = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(weeks=3))
        upcoming = CourseRunFactory(course__partner=self.partner, start=now + datetime.timedelta(weeks=4))
        course_run_keys = [course_run.key for course_run in [archived, current, starting_soon, upcoming]]

        response = self.get_response({"ordering": ordering})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['objects']['count'], 4)

        course_runs = CourseRun.objects.filter(key__in=course_run_keys).order_by(ordering)
        expected = [self.serialize_course_run(course_run) for course_run in course_runs]
        self.assertEqual(response.data['objects']['results'], expected)

    def test_results_include_aggregation_key(self):
        """ Verify the search results only include the aggregation_key for each document. """
        course_run = CourseRunFactory(course__partner=self.partner, status=CourseRunStatus.Published)
        program = ProgramFactory(partner=self.partner, status=ProgramStatus.Active)

        response = self.get_response()
        assert response.status_code == 200
        response_data = json.loads(response.content.decode('utf-8'))

        expected = sorted(
            ['courserun:{}'.format(course_run.course.key), 'program:{}'.format(program.uuid)]
        )
        actual = sorted(
            [obj.get('aggregation_key') for obj in response_data['objects']['results']]
        )
        assert expected == actual


class TypeaheadSearchViewTests(DefaultPartnerMixin, TypeaheadSerializationMixin, LoginMixin, ElasticsearchTestMixin,
                               SynonymTestMixin, APITestCase):
    path = reverse('api:v1:search-typeahead')

    def get_response(self, query=None, partner=None):
        query_dict = query or {}
        query_dict.update({'partner': partner or self.partner.short_code})
        qs = urllib.parse.urlencode(query_dict)

        url = '{path}?{qs}'.format(path=self.path, qs=qs)
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
        self.assertDictEqual(response_data, {'course_runs': [self.serialize_course_run(course_run)],
                                             'programs': [self.serialize_program(program)]})

    def test_typeahead_multiple_results(self):
        """ Verify the typeahead responses always returns a limited number of results, even if there are more hits. """
        RESULT_COUNT = TypeaheadSearchView.RESULT_COUNT
        title = "Test"
        for i in range(RESULT_COUNT + 1):
            CourseRunFactory(title="{}{}".format(title, i), course__partner=self.partner)
            ProgramFactory(title="{}{}".format(title, i), status=ProgramStatus.Active, partner=self.partner)
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
            CourseRunFactory(title="{}{}{}".format(title, course1.title, i), course=course1)
        for i in range(RESULT_COUNT):
            CourseRunFactory(title="{}{}{}".format(title, course2.title, i), course=course2)
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
        self.assertDictEqual(response_data, {'course_runs': [self.serialize_course_run(course_run)],
                                             'programs': [self.serialize_program(program)]})

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
            'course_runs': [self.serialize_course_run(course_run)],
            'programs': [self.serialize_program(program)]
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
            'course_runs': [self.serialize_course_run(course_run)],
            'programs': [self.serialize_program(program)]
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
            'programs': [self.serialize_program(program)]
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
        course_run = CourseRunFactory(authoring_organizations=authoring_organizations, course__partner=self.partner)
        program = ProgramFactory(authoring_organizations=authoring_organizations, partner=self.partner)
        partial_key = authoring_organizations[0].key[0:5]

        response = self.get_response({'q': partial_key})
        self.assertEqual(response.status_code, 200)
        expected = {
            'course_runs': [self.serialize_course_run(course_run)],
            'programs': [self.serialize_program(program)]
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
            'course_runs': [self.serialize_course_run(mit_run),
                            self.serialize_course_run(harvard_run)],
            'programs': [self.serialize_program(mit_program),
                         self.serialize_program(harvard_program)]
        }
        self.assertDictEqual(response.data, expected)

    def test_typeahead_partner_filter(self):
        """ Ensure that a partner param limits results to that partner. """
        course_runs = []
        programs = []

        for partner in ['edx', 'other']:
            title = 'Belongs to partner ' + partner
            partner = PartnerFactory(short_code=partner)
            course_runs.append(CourseRunFactory(title=title, course=CourseFactory(partner=partner)))
            programs.append(ProgramFactory(
                title=title, partner=partner,
                status=ProgramStatus.Active
            ))
        response = self.get_response({'q': 'partner'}, 'edx')
        self.assertEqual(response.status_code, 200)
        edx_course_run = course_runs[0]
        edx_program = programs[0]
        self.assertDictEqual(response.data, {'course_runs': [self.serialize_course_run(edx_course_run)],
                                             'programs': [self.serialize_program(edx_program)]})
