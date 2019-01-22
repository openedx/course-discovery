import datetime
import json

import ddt
import pytest
import pytz
import responses
from django.db import IntegrityError
from django.db.models.functions import Lower
from mock import mock
from rest_framework.reverse import reverse
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.api.v1.views.courses import logger as course_logger
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseEntitlement
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, ProgramFactory, SeatFactory
)


@ddt.ddt
@pytest.mark.usefixtures('django_cache')
class CourseViewSetTests(SerializationMixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory(partner=self.partner)
        self.org = OrganizationFactory(key='edX')

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(27):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_uuid(self):
        """ Verify the endpoint returns the details for a single course with UUID. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.uuid})

        with self.assertNumQueries(27):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no deleted associated programs """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        with self.assertNumQueries(18):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.get('programs'), [])

    def test_get_include_deleted_programs(self):
        """
        Verify the endpoint returns associated deleted programs
        with the 'include_deleted_programs' flag set to True
        """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url += '?include_deleted_programs=1'
        with self.assertNumQueries(31):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.data,
                self.serialize_course(self.course, extra_context={'include_deleted_programs': True})
            )

    def test_get_include_hidden_course_runs(self):
        """
        Verify the endpoint returns associated hidden course runs
        with the 'include_hidden_course_runs' flag set to True
        """
        CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            hidden=True,
            course=self.course
        )
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url += '?include_hidden_course_runs=1'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            self.serialize_course(self.course)
        )

    @ddt.data(1, 0)
    def test_marketable_course_runs_only(self, marketable_course_runs_only):
        """
        Verify that a client requesting marketable_course_runs_only only receives
        course runs that are published, have seats, and can still be enrolled in.
        """
        # Published course run with a seat, no enrollment start or end, and an end date in the future.
        enrollable_course_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            course=self.course
        )
        SeatFactory(course_run=enrollable_course_run)

        # Unpublished course run with a seat.
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=self.course)
        SeatFactory(course_run=unpublished_course_run)

        # Published course run with no seats.
        no_seats_course_run = CourseRunFactory(status=CourseRunStatus.Published, course=self.course)

        # Published course run with a seat and an end date in the past.
        closed_course_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10),
            course=self.course
        )
        SeatFactory(course_run=closed_course_run)

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?marketable_course_runs_only={}'.format(url, marketable_course_runs_only)
        response = self.client.get(url)

        assert response.status_code == 200

        if marketable_course_runs_only:
            # Emulate prefetching behavior.
            for course_run in (unpublished_course_run, no_seats_course_run, closed_course_run):
                course_run.delete()

        assert response.data == self.serialize_course(self.course)

    @ddt.data(1, 0)
    def test_marketable_enrollable_course_runs_with_archived(self, marketable_enrollable_course_runs_with_archived):
        """ Verify the endpoint filters course runs to those that are marketable and
        enrollable, including archived course runs (with an end date in the past). """

        past = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)

        course_run = CourseRunFactory(enrollment_start=None, enrollment_end=future, course=self.course)
        SeatFactory(course_run=course_run)

        filtered_course_runs = [
            CourseRunFactory(enrollment_start=None, enrollment_end=None, course=self.course),
            CourseRunFactory(
                enrollment_start=past, enrollment_end=future, course=self.course
            ),
            CourseRunFactory(enrollment_start=future, course=self.course),
            CourseRunFactory(enrollment_end=past, course=self.course),
        ]

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?marketable_enrollable_course_runs_with_archived={}'.format(
            url, marketable_enrollable_course_runs_with_archived
        )
        response = self.client.get(url)

        assert response.status_code == 200

        if marketable_enrollable_course_runs_with_archived:
            # Emulate prefetching behavior.
            for course_run in filtered_course_runs:
                course_run.delete()

        assert response.data == self.serialize_course(self.course)

    @ddt.data(1, 0)
    def test_get_include_published_course_run(self, published_course_runs_only):
        """
        Verify the endpoint returns hides unpublished programs if
        the 'published_course_runs_only' flag is set to True
        """
        CourseRunFactory(status=CourseRunStatus.Published, course=self.course)
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=self.course)

        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        url = '{}?published_course_runs_only={}'.format(url, published_course_runs_only)

        response = self.client.get(url)

        assert response.status_code == 200

        if published_course_runs_only:
            # Emulate prefetching behavior.
            unpublished_course_run.delete()

        assert response.data == self.serialize_course(self.course)

    def test_list(self):
        """ Verify the endpoint returns a list of all courses. """
        url = reverse('api:v1:course-list')

        with self.assertNumQueries(32):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertListEqual(
                response.data['results'],
                self.serialize_course(Course.objects.all().order_by(Lower('key')), many=True)
            )

    def test_list_query(self):
        """ Verify the endpoint returns a filtered list of courses """
        title = 'Some random title'
        courses = CourseFactory.create_batch(3, title=title)
        courses = sorted(courses, key=lambda course: course.key.lower())
        query = 'title:' + title
        url = '{root}?q={query}'.format(root=reverse('api:v1:course-list'), query=query)

        with self.assertNumQueries(54):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(56):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_uuid_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified uuid. """
        courses = CourseFactory.create_batch(3, partner=self.partner)
        courses = sorted(courses, key=lambda course: course.key.lower())
        uuids = ','.join([str(course.uuid) for course in courses])
        url = '{root}?uuids={uuids}'.format(root=reverse('api:v1:course-list'), uuids=uuids)

        with self.assertNumQueries(56):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = reverse('api:v1:course-list') + '?exclude_utm=1'

        response = self.client.get(url)
        context = {'exclude_utm': 1}
        self.assertEqual(
            response.data['results'],
            self.serialize_course([self.course], many=True, extra_context=context)
        )

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating a person. """
        self.client.logout()
        Course.objects.all().delete()

        url = reverse('api:v1:course-list')
        response = self.client.post(url)
        assert response.status_code == 403
        assert Course.objects.count() == 0

    @responses.activate
    def test_create_with_authentication(self):
        responses.add(
            responses.POST,
            self.partner.lms_url + '/oauth2/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': self.org.key,
            'mode': 'verified',
            'price': 100,
        }
        ecom_url = self.partner.ecommerce_api_url + 'products/'
        ecom_entitlement_data = {
            'product_class': 'Course Entitlement',
            'title': course_data['title'],
            'price': course_data['price'],
            'certificate_type': course_data['mode'],
            'uuid': '00000000-0000-0000-0000-000000000000',
            'stockrecords': [{'partner_sku': 'ABC123'}],
        }
        responses.add(
            responses.POST,
            ecom_url,
            body=json.dumps(ecom_entitlement_data),
            content_type='application/json',
            status=201,
            match_querystring=True
        )
        response = self.client.post(url, course_data, format='json')

        course = Course.objects.last()
        self.assertDictEqual(response.data, self.serialize_course(course))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(course.title, course_data['title'])
        expected_course_key = '{org}+{number}'.format(org=course_data['org'], number=course_data['number'])
        self.assertEqual(course.key, expected_course_key)
        self.assertEqual(course.title, course_data['title'])
        self.assertEqual(1, CourseEntitlement.objects.count())

    def test_create_fails_with_missing_field(self):
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'org': self.org.key,
            'mode': 'audit',
        }
        response = self.client.post(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Missing value for: [number].'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_org(self):
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': 'fake org',
            'mode': 'audit',
        }
        response = self.client.post(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Organization does not exist.'
        self.assertEqual(response.data, expected_error_message)

    def test_create_fails_with_nonexistent_mode(self):
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': self.org.key,
            'mode': 'fake mode',
        }
        response = self.client.post(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        expected_error_message = 'Incorrect data sent. Entitlement Track does not exist.'
        self.assertEqual(response.data, expected_error_message)

    @ddt.data(
        (
            {'title': 'Course title', 'number': 'test101', 'org': 'fake org', 'mode': 'fake mode'},
            'Incorrect data sent. Organization does not exist. Entitlement Track does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'edX', 'mode': 'fake mode'},
            'Incorrect data sent. Missing value for: [number]. Entitlement Track does not exist.'
        ),
        (
            {'title': 'Course title', 'org': 'fake org', 'mode': 'audit'},
            'Incorrect data sent. Missing value for: [number]. Organization does not exist.'
        ),
        (
            {'number': 'test101', 'org': 'fake org', 'mode': 'fake mode'},
            'Incorrect data sent. Missing value for: [title]. Organization does not exist. '
            'Entitlement Track does not exist.'
        ),
    )
    @ddt.unpack
    def test_create_fails_with_multiple_errors(self, course_data, expected_error_message):
        url = reverse('api:v1:course-list')
        response = self.client.post(url, course_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, expected_error_message)

    def test_create_with_api_exception(self):
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': self.org.key,
            'mode': 'audit',
        }
        with mock.patch(
            'course_discovery.apps.api.v1.views.courses.CourseViewSet.perform_create',
            side_effect=IntegrityError
        ):
            with LogCapture(course_logger.name) as log_capture:
                response = self.client.post(url, course_data, format='json')
                self.assertEqual(response.status_code, 400)
                log_capture.check(
                    (
                        course_logger.name,
                        'ERROR',
                        'An error occurred while creating the Course [{title}].'.format(title=course_data['title'])
                    )
                )

    @responses.activate
    def test_create_with_ecom_api_exception(self):
        responses.add(
            responses.POST,
            self.partner.lms_url + '/oauth2/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )
        url = reverse('api:v1:course-list')
        course_data = {
            'title': 'Course title',
            'number': 'test101',
            'org': self.org.key,
            'mode': 'verified',
            'price': 100,
        }
        ecom_url = self.partner.ecommerce_api_url + 'products/'
        expected_error_message = 'Missing or bad value for: [title].'
        responses.add(
            responses.POST,
            ecom_url,
            body=expected_error_message,
            status=400,
        )
        with LogCapture(course_logger.name) as log_capture:
            response = self.client.post(url, course_data, format='json')
            self.assertEqual(response.status_code, 400)
            log_capture.check(
                (
                    course_logger.name,
                    'ERROR',
                    'The following error occurred while creating the Course Entitlement in E-commerce: '
                    '{ecom_error}'.format(ecom_error=expected_error_message)
                )
            )
