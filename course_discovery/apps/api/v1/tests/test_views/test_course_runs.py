# pylint: disable=no-member
import datetime
import urllib

import ddt
import pytz
from django.conf import settings
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import (
    CourseRunFactory, PartnerFactory, ProgramFactory, SeatFactory
)


@ddt.ddt
class CourseRunViewSetTests(SerializationMixin, ElasticsearchTestMixin, APITestCase):
    def setUp(self):
        super(CourseRunViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.user)
        # DEFAULT_PARTNER_ID is used explicitly here to avoid issues with differences in
        # auto-incrementing behavior across databases. Otherwise, it's not safe to assume
        # that the partner created here will always have id=DEFAULT_PARTNER_ID.
        self.partner = PartnerFactory(id=settings.DEFAULT_PARTNER_ID)
        self.course_run = CourseRunFactory(course__partner=self.partner)
        self.course_run_2 = CourseRunFactory(course__partner=self.partner)
        self.refresh_index()
        self.request = APIRequestFactory().get('/')
        self.request.user = self.user

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(10):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertEqual(response.data, self.serialize_course_run(self.course_run))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no associated deleted programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(11):
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

        with self.assertNumQueries(13):
            response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == \
            self.serialize_course_run(self.course_run, extra_context={'include_deleted_programs': True})

    def test_get_exclude_unpublished_programs(self):
        """ Verify the endpoint returns no associated unpublished programs """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)

        url = reverse('api:v1:course_run-detail', kwargs={'key': self.course_run.key})

        with self.assertNumQueries(11):
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

        with self.assertNumQueries(13):
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

        with self.assertNumQueries(11):
            response = self.client.get(url)

        assert response.status_code == 200
        self.assertListEqual(
            response.data['results'],
            self.serialize_course_run(CourseRun.objects.all().order_by(Lower('key')), many=True)
        )

    def test_list_sorted_by_course_start_date(self):
        """ Verify the endpoint returns a list of all course runs sorted by start date. """
        url = '{root}?ordering=start'.format(root=reverse('api:v1:course_run-list'))

        with self.assertNumQueries(11):
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

        with self.assertNumQueries(36):
            response = self.client.get(url)

        actual_sorted = sorted(response.data['results'], key=lambda course_run: course_run['key'])
        expected_sorted = sorted(self.serialize_course_run(course_runs, many=True),
                                 key=lambda course_run: course_run['key'])
        self.assertListEqual(actual_sorted, expected_sorted)

    def test_list_query_invalid_partner(self):
        """ Verify the endpoint returns an 400 BAD_REQUEST if an invalid partner is sent """
        query = 'title:Some random title'
        url = '{root}?q={query}&partner={partner}'.format(root=reverse('api:v1:course_run-list'), query=query,
                                                          partner='foo')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

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

    def test_contains_single_course_run_invalid_partner(self):
        """ Verify that a 400 BAD_REQUEST is thrown when passing an invalid partner """
        qs = urllib.parse.urlencode({
            'query': 'id:course*',
            'course_run_ids': self.course_run.key,
            'partner': 'foo'
        })
        url = '{}?{}'.format(reverse('api:v1:course_run-contains'), qs)

        response = self.client.get(url)
        assert response.status_code == 400

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
