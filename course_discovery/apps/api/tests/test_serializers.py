from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer, ContainedCoursesSerializer
from course_discovery.apps.core.tests.factories import CatalogFactory, CourseFactory


class CatalogSerializerTests(TestCase):
    def test_data(self):
        catalog = CatalogFactory()
        path = reverse('api:v1:catalog-detail', kwargs={'id': catalog.id})
        request = RequestFactory().get(path)
        serializer = CatalogSerializer(catalog, context={'request': request})

        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
            'url': request.build_absolute_uri(),
        }
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        path = reverse('api:v1:course-detail', kwargs={'id': course.id})
        request = RequestFactory().get(path)
        serializer = CourseSerializer(course, context={'request': request})

        expected = {
            'id': course.id,
            'name': course.name,
            'url': request.build_absolute_uri(),
        }
        self.assertDictEqual(serializer.data, expected)


class ContainedCoursesSerializerTests(TestCase):
    def test_data(self):
        instance = {
            'courses': {
                'course-v1:edX+DemoX+Demo_Course': True,
                'a/b/c': False
            }
        }
        serializer = ContainedCoursesSerializer(instance)
        self.assertDictEqual(serializer.data, instance)
