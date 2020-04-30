# pylint: disable=no-member
import datetime
import urllib

import ddt
import pytz
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory, SeatFactory


@ddt.ddt
class CourseRunViewSetTests(SerializationMixin, ElasticsearchTestMixin, APITestCase):
    def setUp(self):
        super(CourseRunViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.edx_org_short_name = 'edx'
        self.client.force_authenticate(self.user)
        self.course_run = CourseRunFactory(course__partner=self.partner)
        self.course_run_2 = CourseRunFactory(course__partner=self.partner)
        # Course_run of edx organization
        self.course_run_3 = CourseRunFactory(
            course__partner=self.partner,
            course__authoring_organizations__key=self.edx_org_short_name
        )
        self.refresh_index()
        self.request = APIRequestFactory().get('/')
        self.request.user = self.user

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(11):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertEqual(response.data, self.serialize_course_run(self.course_run))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no associated deleted programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(12):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data.get('programs') == []

    def test_get_include_deleted_programs(self):
        """
        Verify the endpoint returns associated deleted programs
        with the 'include_deleted_programs' flag set to True
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        url += '?include_deleted_programs=1'

        with self.assertNumQueries(17):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == \
            self.serialize_course_run(self.course_run, extra_context={'include_deleted_programs': True})

    def test_get_exclude_unpublished_programs(self):
        """ Verify the endpoint returns no associated unpublished programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(12):
            response = self.client.get(url)
            assert response.status_code == 200
            assert response.data.get('programs') == []

    def test_get_include_unpublished_programs(self):
        """
        Verify the endpoint returns associated unpublished programs
        with the 'include_unpublished_programs' flag set to True
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})
        url += '?include_unpublished_programs=1'

        with self.assertNumQueries(17):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == \
            self.serialize_course_run(self.course_run, extra_context={'include_unpublished_programs': True})

    def test_partial_update(self):
        """ Verify the endpoint supports partially updating a course_run's fields, provided user has permission. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        expected_min_effort = 867
        expected_max_effort = 5309
        data = {
            'max_effort': expected_max_effort,
            'min_effort': expected_min_effort,
        }

        # Update this course_run with the new info
        response = self.client.patch(url, data, format='json')
        assert response.status_code == 200

        # refresh and make sure we have the new effort levels
        self.course_run.refresh_from_db()

        assert self.course_run.max_effort == expected_max_effort
        assert self.course_run.min_effort == expected_min_effort

    def test_partial_update_bad_permission(self):
        """ Verify partially updating will fail if user doesn't have permission. """
        user = UserFactory(is_staff=False, is_superuser=False)
        self.client.force_authenticate(user)
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        response = self.client.patch(url, {}, format='json')
        assert response.status_code == 403

    def test_list(self):
        """ Verify the endpoint returns a list of all course runs. """
        url = reverse('api:v1:course_run-list')

        with self.assertNumQueries(13):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by(Lower('key')), many=True)
        )

    def test_list_edx_org_short_name_filter(self):
        """
        Verify course runs filtering on edX organization.
        """
        course_run_api_url_with_org_filter = '{course_run_api_url}?org={edx_org_short_name}'.format(
            course_run_api_url=reverse('api:v1:course_run-list'),
            edx_org_short_name=self.edx_org_short_name
        )
        expected_serialized_course_runs = self.serialize_course_run(
            CourseRun.objects.filter(course__authoring_organizations__key=self.edx_org_short_name).order_by(Lower('key')),
            many=True
        )

        response = self.client.get(course_run_api_url_with_org_filter)
        assert response.status_code == 200
        course_runs_from_response = response.data['results']
        assert course_runs_from_response == expected_serialized_course_runs

    def test_list_sorted_by_course_start_date(self):
        """ Verify the endpoint returns a list of all course runs sorted by start date. """
        url = '{root}?ordering=start'.format(root=reverse('api:v1:course_run-list'))

        with self.assertNumQueries(13):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by('start'), many=True)
        )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        course_runs = CourseRunFactory.create_batch(3, title='Some random title', course__partner=self.partner)
        CourseRunFactory(title='non-matching name')
        query = 'title:Some random title'
        url = '{root}?q={query}'.format(root=reverse('api:v1:course_run-list'), query=query)

        with self.assertNumQueries(39):
            response = self.client.get(url)

        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(self.serialize_course_run(course_runs, many=True),
                                 key=lambda course_run: course_run['key'])
        self.assertListEqual(actual_sorted, expected_sorted)

    def assert_list_results(self, url, expected, extra_context=None):
        expected = sorted(expected, key=lambda course_run: course_run.key.lower())
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(expected, many=True, extra_context=extra_context)
        )

    def test_filter_by_keys(self):
        """ Verify the endpoint returns a list of course runs filtered by the specified keys. """
        CourseRun.objects.all().delete()
        expected = CourseRunFactory.create_batch(3, course__partner=self.partner)
        keys = ','.join([course.key for course in expected])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course_run-list'), keys=keys)
        self.assert_list_results(url, expected)

    def test_filter_by_marketable(self):
        """ Verify the endpoint filters course runs to those that are marketable. """
        CourseRun.objects.all().delete()
        expected = CourseRunFactory.create_batch(3, course__partner=self.partner)
        for course_run in expected:
            SeatFactory(course_run=course_run)

        CourseRunFactory.create_batch(3, slug=None, course__partner=self.partner)
        CourseRunFactory.create_batch(3, slug='', course__partner=self.partner)

        url = reverse('api:v1:course_run-list') + '?marketable=1'
        self.assert_list_results(url, expected)

    def test_filter_by_hidden(self):
        """ Verify the endpoint filters course runs that are hidden. """
        CourseRun.objects.all().delete()
        course_runs = CourseRunFactory.create_batch(3, course__partner=self.partner)
        hidden_course_runs = CourseRunFactory.create_batch(3, hidden=True, course__partner=self.partner)
        url = reverse('api:v1:course_run-list')
        self.assert_list_results(url, course_runs + hidden_course_runs)
        url = reverse('api:v1:course_run-list') + '?hidden=False'
        self.assert_list_results(url, course_runs)

    def test_filter_by_active(self):
        """ Verify the endpoint filters course runs to those that are active. """
        CourseRun.objects.all().delete()

        # Create course with end date in future and enrollment_end in past.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        CourseRunFactory(end=end, enrollment_end=enrollment_end, course__partner=self.partner)

        # Create course with end date in past and no enrollment_end.
        end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        CourseRunFactory(end=end, enrollment_end=None, course__partner=self.partner)

        # Create course with end date in future and enrollment_end in future.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        active_enrollment_end = CourseRunFactory(end=end, enrollment_end=enrollment_end, course__partner=self.partner)

        # Create course with end date in future and no enrollment_end.
        active_no_enrollment_end = CourseRunFactory(end=end, enrollment_end=None, course__partner=self.partner)

        expected = [active_enrollment_end, active_no_enrollment_end]
        url = reverse('api:v1:course_run-list') + '?active=1'
        self.assert_list_results(url, expected)

    def test_filter_by_license(self):
        CourseRun.objects.all().delete()
        course_runs_cc = CourseRunFactory.create_batch(3, course__partner=self.partner, license='cc-by-sa')
        CourseRunFactory.create_batch(3, course__partner=self.partner, license='')

        url = reverse('api:v1:course_run-list') + '?license=cc-by-sa'
        self.assert_list_results(url, course_runs_cc)

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = reverse('api:v1:course_run-list') + '?exclude_utm=1'
        self.assert_list_results(url, CourseRun.objects.all(), extra_context={'exclude_utm': 1})

    def test_contains_single_course_run(self):
        """ Verify that a single course_run is contained in a query """
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': self.course_run.key,
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)
        response = self.client.get(url)
        assert response.status_code == 200
        self.assertEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True
                }
            }
        )

    def test_contains_multiple_course_runs(self):
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': '{},{},{}'.format(self.course_run.key, self.course_run_2.key, 'abc')
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        assert response.status_code == 200
        self.assertDictEqual(
            response.data,
            {
                'course_runs': {
                    self.course_run.key: True,
                    self.course_run_2.key: True,
                    'abc': False
                }
            }
        )

    def test_contains_multiple_course_runs_edx_org_short_name_filter(self):
        """
        Verify contained course runs filtering on edX organization.
        """
        edx_org_course_run_key = 'course-v1:edX+DemoX+Demo_Course'
        elastic_search_query_string_with_org_filter = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': '{course_run_1_key},{course_run_2_key},{course_run_3_key}'.format(
                course_run_1_key=self.course_run_2.key,
                course_run_2_key=self.course_run_3.key,
                course_run_3_key=edx_org_course_run_key
            ),
            'org': self.edx_org_short_name
        })
        course_run_api_url_with_org_filter = '{course_run_api_url}?{elastic_search_query_string_with_org_filter}'.format(
            course_run_api_url=reverse('api:v1:course_run-contains'),
            elastic_search_query_string_with_org_filter=elastic_search_query_string_with_org_filter
        )
        expected_serialized_contained_course_runs = {
            'course_runs': {
                self.course_run_2.key: False,
                self.course_run_3.key: False,
                edx_org_course_run_key: False
            }
        }

        response = self.client.get(course_run_api_url_with_org_filter)
        assert response.status_code == 200
        course_runs_from_response = response.data
        assert course_runs_from_response == expected_serialized_contained_course_runs

    @ddt.data(
        {'params': {'course_run_ids': 'a/b/c'}},
        {'params': {'query': 'id:course*'}},
        {'params': {}}
    )
    @ddt.unpack
    def test_contains_missing_parameter(self, params):
        qs = urllib.parse.urlencode(params)
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        assert response.status_code == 400
