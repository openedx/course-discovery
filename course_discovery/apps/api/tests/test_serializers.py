from django.test import TestCase

from course_discovery.apps.api.serializers import CatalogSerializer, CourseSerializer, ContainedCoursesSerializer
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class CatalogSerializerTests(TestCase):
    def test_data(self):
        catalog = CatalogFactory(query='*:*')  # We intentionally use a query for all Courses.
        courses = CourseFactory.create_batch(10)
        serializer = CatalogSerializer(catalog)

        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
            'courses_count': len(courses)
        }
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        serializer = CourseSerializer(course)

        expected = {
            'key': course.key,
            'title': course.title,
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
