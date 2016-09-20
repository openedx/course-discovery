from django.db.models.functions import Lower
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class CourseViewSetTests(SerializationMixin, APITestCase):
    def setUp(self):
        super(CourseViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactory()

    def test_get(self):
        """ Verify the endpoint returns the details for a single course. """
        url = reverse('api:v1:course-detail', kwargs={'key': self.course.key})

        with self.assertNumQueries(19):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, self.serialize_course(self.course))

    def test_list(self):
        """ Verify the endpoint returns a list of all courses. """
        url = reverse('api:v1:course-list')

        with self.assertNumQueries(25):
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

        with self.assertNumQueries(62):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))

    def test_list_key_filter(self):
        """ Verify the endpoint returns a list of courses filtered by the specified keys. """
        courses = CourseFactory.create_batch(3)
        courses = sorted(courses, key=lambda course: course.key.lower())
        keys = ','.join([course.key for course in courses])
        url = '{root}?keys={keys}'.format(root=reverse('api:v1:course-list'), keys=keys)

        with self.assertNumQueries(38):
            response = self.client.get(url)
            self.assertListEqual(response.data['results'], self.serialize_course(courses, many=True))
