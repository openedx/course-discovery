from django.test import TestCase

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer, ContainedCoursesSerializer
from course_discovery.apps.catalogs.tests.factories import CatalogFactory


class CatalogSerializerTests(TestCase):
    def test_data(self):
        catalog = CatalogFactory()
        serializer = CatalogSerializer(catalog)
        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
        }
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = {
            'id': 'course-v1:edX+DemoX+Demo_Course',
            'name': 'edX Demo Course',
        }
        serializer = CourseSerializer(course)
        self.assertDictEqual(serializer.data, course)


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
