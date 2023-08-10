import datetime
import json
import urllib.parse
from collections import defaultdict
from unittest import mock

import ddt
import pytz
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import (
    APITestCase, LoginMixin, SerializationMixin, SynonymTestMixin
)
from course_discovery.apps.api.v1.tests.test_views.test_search import ElasticsearchTestMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    AdditionalPromoArea, Course, CourseRun, Curriculum, CurriculumCourseMembership, CurriculumCourseRunExclusion, Image,
    LevelType, Organization, Program, ProgramType, SeatType, Video
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, CurriculumCourseMembershipFactory, CurriculumCourseRunExclusionFactory,
    CurriculumFactory, OrganizationFactory, ProgramFactory, ProgramTypeFactory, SeatTypeFactory
)
from course_discovery.apps.edx_catalog_extensions.api.serializers import DistinctCountsAggregateFacetSearchSerializer
from course_discovery.apps.edx_catalog_extensions.api.v1.views import ProgramFixtureView
from course_discovery.apps.ietf_language_tags.models import LanguageTag


class DistinctCountsAggregateSearchViewSetTests(SerializationMixin, LoginMixin,
                                                ElasticsearchTestMixin, SynonymTestMixin, APITestCase):
    path = reverse('extensions:api:v1:search-all-facets')

    def get_response(self, query=None):
        query = urllib.parse.urlencode(query) if query else ''
        url = f'{self.path}?{query}'
        return self.client.get(url)

    def process_response(self, query):
        response = self.get_response(query).data
        assert response['objects']['count']
        return response['objects']

    def build_courserun(self, **kwargs):
        """ Build a CourseRun that will be visible in search results."""
        kwargs.update({'status': CourseRunStatus.Published, 'hidden': False})
        return CourseRunFactory(**kwargs)

    def build_program(self, **kwargs):
        """ Build a Program that will be visible in search results."""
        kwargs.update({'status': ProgramStatus.Active})
        return ProgramFactory(**kwargs)

    def assert_url_path_and_query(self, url, expected_path, expected_query):
        """ Verify that the URL contains the expected path and query parameters."""
        parsed_url = urllib.parse.urlparse(url)
        parsed_query = urllib.parse.parse_qs(parsed_url.query)

        assert expected_path == parsed_url.path
        for key, values in parsed_query.items():
            assert key in expected_query
            assert sorted(values) == sorted(expected_query[key])

    def test_authentication(self):
        """ Verify the endpoint requires authentication."""
        self.client.logout()
        response = self.get_response()
        assert response.status_code == 401

    def test_field_facet_response(self):
        """ Verify that field facets are included in the response and that they are properly formatted."""
        for course in [CourseFactory(partner=self.partner), CourseFactory(partner=self.partner)]:
            self.build_courserun(course=course)
            self.build_courserun(course=course)
        self.build_program(partner=self.partner)

        response = self.get_response()
        assert response.status_code == 200

        expected_facets = DistinctCountsAggregateFacetSearchSerializer.Meta.field_options.keys()
        assert sorted(expected_facets) == sorted(response.data['fields'].keys())

        content_types = {facet['text']: facet for facet in response.data['fields']['content_type']}
        assert content_types['courserun']['count'] == 4
        assert content_types['courserun']['distinct_count'] == 2
        narrow_url = content_types['courserun']['narrow_url']
        self.assert_url_path_and_query(narrow_url, self.path, {'selected_facets': ['content_type_exact:courserun']})

        assert content_types['program']['count'] == 1
        assert content_types['program']['distinct_count'] == 1
        narrow_url = content_types['program']['narrow_url']
        self.assert_url_path_and_query(narrow_url, self.path, {'selected_facets': ['content_type_exact:program']})

    def test_query_facet_response(self):
        """ Verify that query facets are included in the response and that they are properly formatted."""
        now = datetime.datetime.now(pytz.UTC)
        current = (now - datetime.timedelta(days=1), now + datetime.timedelta(days=1))
        starting_soon = (now + datetime.timedelta(days=1), now + datetime.timedelta(days=2))
        upcoming = (now + datetime.timedelta(days=61), now + datetime.timedelta(days=62))
        archived = (now - datetime.timedelta(days=2), now - datetime.timedelta(days=1))

        for dates in [current, starting_soon, upcoming, archived]:
            course = CourseFactory(partner=self.partner)
            # Create two CourseRuns so that we can see that the distinct_count differs from the normal count
            self.build_courserun(start=dates[0], end=dates[1], course=course)
            self.build_courserun(start=dates[0], end=dates[1], course=course)

        response = self.get_response()
        assert response.status_code == 200

        expected_facets = DistinctCountsAggregateFacetSearchSerializer.Meta.field_queries.keys()
        for facet_name in expected_facets:
            facet = response.data['queries'][facet_name]
            assert facet['count'] == 2
            assert facet['distinct_count'] == 1
            self.assert_url_path_and_query(facet['narrow_url'], self.path, {'selected_query_facets': [facet_name]})

    def test_objects_response(self):
        """ Verify that objects are included in the response and that they are properly formatted."""
        course_runs, programs = {}, {}
        for course in [CourseFactory(partner=self.partner), CourseFactory(partner=self.partner)]:
            run1 = self.build_courserun(course=course)
            course_runs[str(run1.key)] = run1

            run2 = self.build_courserun(course=course)
            course_runs[str(run2.key)] = run2

            program = self.build_program(partner=self.partner)
            programs[str(program.uuid)] = program

        # Using page_size: 5 guarantees at lease one program will be included in the response
        response = self.get_response({'page_size': 5})
        assert response.status_code == 200

        objects = response.data['objects']
        assert objects['count'] == 6
        assert objects['distinct_count'] == 4
        self.assert_url_path_and_query(objects['next'], self.path, {'page': ['2'], 'page_size': ['5']})

        for record in objects['results']:
            if record['content_type'] == 'courserun':
                assert record == self.serialize_course_run_search(course_runs[str(record['key'])])
            else:
                assert record == self.serialize_program_search(programs[str(record['uuid'])])

    def test_response_with_search_query(self):
        """ Verify that the response is accurate when a search query is passed."""
        now = datetime.datetime.now(pytz.UTC)
        current = (now - datetime.timedelta(days=1), now + datetime.timedelta(days=1))

        course = CourseFactory(partner=self.partner)
        run_1 = self.build_courserun(title='foo', course=course, start=current[0], end=current[1])
        run_2 = self.build_courserun(title='foo', course=course, start=current[0], end=current[1])
        program = self.build_program(title='foo', partner=self.partner)

        # These should be excluded from the result set
        self.build_courserun(title='bar', start=current[0], end=current[1], course=course)
        self.build_program(title='bar', partner=self.partner)

        response = self.get_response({'q': 'foo'})
        assert response.status_code == 200

        objects = response.data['objects']
        assert objects['count'] == 3
        assert objects['distinct_count'] == 2
        expected = sorted([run_1.key, run_2.key, str(program.uuid)])
        actual = sorted([r['key'] if r['content_type'] == 'courserun' else str(r['uuid']) for r in objects['results']])
        assert expected == actual

        content_types = {facet['text']: facet for facet in response.data['fields']['content_type']}
        assert content_types['courserun']['count'] == 2
        assert content_types['courserun']['distinct_count'] == 1
        expected_query_params = {'q': ['foo'], 'selected_facets': ['content_type_exact:courserun']}
        self.assert_url_path_and_query(content_types['courserun']['narrow_url'], self.path, expected_query_params)

        availability_current = response.data['queries']['availability_current']
        assert availability_current['count'] == 2
        assert availability_current['distinct_count'] == 1
        expected_query_params = {'q': ['foo'], 'selected_query_facets': ['availability_current']}
        self.assert_url_path_and_query(availability_current['narrow_url'], self.path, expected_query_params)

    def test_pagination(self):
        """ Verify that the response is paginated correctly."""
        for i, course in enumerate([CourseFactory(partner=self.partner), CourseFactory(partner=self.partner)]):
            self.build_courserun(title=f'{i}a', course=course)
            self.build_courserun(title=f'{i}b', course=course)
            self.build_courserun(title=f'{i}c', course=course)
        self.build_program(title='program', partner=self.partner)

        response_all = self.get_response()
        response_paginated = self.get_response({'page': 2, 'page_size': 2})

        assert response_all.data['objects']['count'] == 7
        assert response_paginated.data['objects']['count'] == 7

        assert response_all.data['objects']['distinct_count'] == 3
        assert response_paginated.data['objects']['distinct_count'] == 3

        expected = sorted([record['title'] for record in response_all.data['objects']['results'][2:4]])
        actual = sorted([record['title'] for record in response_paginated.data['objects']['results']])
        assert expected == actual
        expected_query_params = {'page': ['3'], 'page_size': ['2']}
        self.assert_url_path_and_query(response_paginated.data['objects']['next'], self.path, expected_query_params)

    def test_selected_field_facet(self):
        """ Verify that the response is accurate when a field facet is selected."""
        now = datetime.datetime.now(pytz.UTC)
        current = (now - datetime.timedelta(days=1), now + datetime.timedelta(days=1))
        archived = (now - datetime.timedelta(days=2), now - datetime.timedelta(days=1))

        course = CourseFactory(partner=self.partner)
        run_1 = self.build_courserun(course=course, start=current[0], end=current[1], pacing_type='self_paced')
        run_2 = self.build_courserun(course=course, start=archived[0], end=archived[1], pacing_type='self_paced')
        run_3 = self.build_courserun(course=course, start=current[0], end=current[1], pacing_type='instructor_paced')
        run_4 = self.build_courserun(course=course, start=archived[0], end=archived[1], pacing_type='instructor_paced')
        self.build_program(partner=self.partner)

        response = self.get_response({'selected_facets': 'content_type_exact:courserun'})
        assert response.status_code == 200

        assert response.data['objects']['count'] == 4
        assert response.data['objects']['distinct_count'] == 1
        expected = sorted([run_1.key, run_2.key, run_3.key, run_4.key])
        actual = sorted([record['key'] for record in response.data['objects']['results']])
        assert expected == actual

        pacing_types = {facet['text']: facet for facet in response.data['fields']['pacing_type']}
        assert pacing_types['self_paced']['count'] == 2
        assert pacing_types['self_paced']['distinct_count'] == 1
        expected_query_params = {'selected_facets': ['content_type_exact:courserun', 'pacing_type_exact:self_paced']}
        self.assert_url_path_and_query(pacing_types['self_paced']['narrow_url'], self.path, expected_query_params)

        availability_current = response.data['queries']['availability_current']
        assert availability_current['count'] == 2
        assert availability_current['distinct_count'] == 1
        expected_query_params = {
            'selected_facets': ['content_type_exact:courserun'],
            'selected_query_facets': ['availability_current'],
        }
        self.assert_url_path_and_query(availability_current['narrow_url'], self.path, expected_query_params)

    def test_selected_query_facet(self):
        """ Verify that the response is accurate when a query facet is selected."""
        now = datetime.datetime.now(pytz.UTC)
        current = (now - datetime.timedelta(days=1), now + datetime.timedelta(days=1))
        archived = (now - datetime.timedelta(days=2), now - datetime.timedelta(days=1))

        course = CourseFactory(partner=self.partner)
        run_1 = self.build_courserun(course=course, start=current[0], end=current[1], pacing_type='self_paced')
        run_2 = self.build_courserun(course=course, start=current[0], end=current[1], pacing_type='self_paced')
        self.build_courserun(course=course, start=archived[0], end=archived[1], pacing_type='self_paced')
        self.build_courserun(course=course, start=archived[0], end=archived[1], pacing_type='instructor_paced')

        response = self.get_response({'selected_query_facets': 'availability_current'})
        assert response.status_code == 200

        assert response.data['objects']['count'] == 2
        assert response.data['objects']['distinct_count'] == 1
        expected = sorted([run_1.key, run_2.key])
        actual = sorted([run['key'] for run in response.data['objects']['results']])
        assert expected == actual

        pacing_types = {facet['text']: facet for facet in response.data['fields']['pacing_type']}
        assert pacing_types['self_paced']['count'] == 2
        assert pacing_types['self_paced']['distinct_count'] == 1
        expected_query_params = {
            'selected_query_facets': ['availability_current'],
            'selected_facets': ['pacing_type_exact:self_paced'],
        }
        self.assert_url_path_and_query(pacing_types['self_paced']['narrow_url'], self.path, expected_query_params)


@ddt.ddt
class ProgramFixtureViewTests(APITestCase):

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.staff = UserFactory(username='staff', is_staff=True)
        seat_type = SeatTypeFactory(name="TestSeatType")
        self.program_type = ProgramTypeFactory(
            name="TestProgramType",
            slug="test-program-type",
            applicable_seat_types=[seat_type],
        )

    def login_user(self):
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def login_staff(self):
        self.client.login(username=self.staff.username, password=USER_PASSWORD)

    @staticmethod
    def queries(n):
        """ Adjust query count for boilerplate queries (user log in, etc.) """
        return n + 3

    def get(self, uuids):
        path = reverse('extensions:api:v1:get-program-fixture')
        if uuids:
            uuids_str = ",".join(str(uuid) for uuid in uuids)
            url = f"{path}?programs={uuids_str}"
        else:
            url = path
        return self.client.get(url)

    def create_program(self, orgs):
        program = ProgramFactory(
            authoring_organizations=orgs, type=self.program_type
        )
        curr = CurriculumFactory(program=program)
        course1_draft = CourseFactory(draft=True)
        course1 = CourseFactory(draft_version=course1_draft)
        _run1a = CourseRunFactory(course=course1)
        _run1b = CourseRunFactory(course=course1)
        course2 = CourseFactory()
        _run2a = CourseRunFactory(course=course2)
        run2b = CourseRunFactory(course=course2)
        _mem1 = CurriculumCourseMembershipFactory(curriculum=curr, course=course1)
        mem2 = CurriculumCourseMembershipFactory(curriculum=curr, course=course2)
        _ex = CurriculumCourseRunExclusionFactory(course_membership=mem2, course_run=run2b)
        return program

    def test_200(self):
        self.login_staff()
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        program1 = self.create_program([org1])
        program2 = self.create_program([org2])
        program12 = self.create_program([org1, org2])
        programs = [program1, program2, program12]
        uuids = [program.uuid for program in programs]

        response = self.get(uuids)
        self.assertEqual(response.status_code, 200)
        fixture = json.loads(response.content.decode('utf-8'))

        # To make this tests less brittle, allow (inclusive) ranges for each model count.
        # For some models (e.g. Course) we DO care about the exact count.
        # For others (e.g. Video) we just want to make sure that they are there,
        # but that we're not loading a crazy amount of them.
        expected_count_ranges_by_model = {
            Organization: (2, 2),
            Program: (3, 3),
            Curriculum: (3, 3),
            Course: (9, 9),
            CourseRun: (12, 12),
            CurriculumCourseMembership: (6, 6),
            CurriculumCourseRunExclusion: (3, 3),
            ProgramType: (1, 1),
            SeatType: (1, 1),
            AdditionalPromoArea: (5, 15),
            Image: (20, 60),
            LevelType: (5, 15),
            Video: (20, 60),
            LanguageTag: (10, 30),
        }

        actual_appearances_by_model_label = defaultdict(set)
        for record in fixture:
            pk = record['pk']
            model_label = record['model']
            # Assert no duplicate objects
            self.assertNotIn(pk, actual_appearances_by_model_label[model_label])
            actual_appearances_by_model_label[model_label].add(pk)

        for model, (min_expected, max_expected) in expected_count_ranges_by_model.items():
            model_label = model._meta.label_lower
            actual_count = len(actual_appearances_by_model_label[model_label])
            err_string = "object count of {} for {} outside expected range [{}, {}]".format(
                actual_count, model_label, min_expected, max_expected
            )
            self.assertGreaterEqual(actual_count, min_expected, err_string)
            self.assertLessEqual(actual_count, max_expected, err_string)

    def test_401(self):
        response = self.get(None)
        self.assertEqual(response.status_code, 401)

    def test_403(self):
        self.login_user()
        response = self.get(None)
        self.assertEqual(response.status_code, 403)

    def test_404_no_programs(self):
        self.login_staff()
        with self.assertNumQueries(self.queries(0)):
            response = self.get(None)
        self.assertEqual(response.status_code, 404)

    def test_422_too_many_programs(self):
        self.login_staff()
        org1 = OrganizationFactory()
        program_1 = self.create_program([org1])
        program_2 = self.create_program([org1])
        with mock.patch.object(ProgramFixtureView, 'MAX_REQUESTED_PROGRAMS', 1):
            with self.assertNumQueries(self.queries(2)):
                response = self.get([program_1.uuid, program_2.uuid])
        self.assertEqual(response.status_code, 422)

    def test_404_bad_input(self):
        self.login_staff()
        with self.assertNumQueries(self.queries(0)):
            response = self.get(['this-is-not-a-uuid'])
        self.assertEqual(response.status_code, 404)

    def test_404_nonexistent(self):
        self.login_staff()
        program = self.create_program([OrganizationFactory()])
        bad_uuid = 'e9222eb7-7218-4a8b-9dff-b42bafbf6ed7'
        with self.assertNumQueries(self.queries(1)):
            response = self.get([program.uuid, bad_uuid])
        self.assertEqual(response.status_code, 404)

    def test_exception_failed_load_objects(self):
        self.login_staff()
        org = OrganizationFactory()
        program = self.create_program([org])
        course_base_manager = Course._base_manager  # pylint: disable=protected-access
        with mock.patch.object(
                course_base_manager,
                'filter',
                autospec=True,
                return_value=course_base_manager.none(),
        ):
            with self.assertRaises(Exception) as ex:
                self.get([program.uuid])
        self.assertIn('Failed to load', str(ex.exception))
