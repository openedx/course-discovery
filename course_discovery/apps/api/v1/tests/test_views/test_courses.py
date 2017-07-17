import datetime

import ddt
import pytz
from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, ProgramFactory, SeatFactory
)


@ddt.ddt
class CourseViewSetTests(SerializationMixin, APITestCase):
    maxDiff = None

    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory()

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(18):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_get_exclude_deleted_programs(self):
        """ Verify the endpoint returns no deleted associated programs """
        ProgramFactory(courses=[self.course], status=ProgramStatus.Deleted)
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})
        with self.assertNumQueries(11):
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
        with self.assertNumQueries(22):
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

        with self.assertNumQueries(24):
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

        with self.assertNumQueries(37):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(37):
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
