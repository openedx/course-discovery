"""
Tests for the models registered in tagging app
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.models import CourseVertical
from course_discovery.apps.tagging.tests.factories import CourseVerticalFactory, SubVerticalFactory, VerticalFactory


class VerticalModelTests(TestCase):
    def setUp(self):
        super().setUp()
        self.vertical = VerticalFactory(name="Test Vertical", is_active=True)

    def test_str(self):
        """ Verify the string representation of a vertical """
        self.assertEqual(str(self.vertical), self.vertical.name)

    def test_unique_name(self):
        """ Verify that vertical names must be unique """
        with self.assertRaises(Exception):
            VerticalFactory(name="Test Vertical")

    def test_vertical_filter_creation(self):
        """ Verify that vertical filter is created correctly """
        self.assertEqual(self.vertical.name, "Test Vertical")
        self.assertTrue(self.vertical.is_active)
        self.assertEqual(self.vertical.slug, "test-vertical")
        self.assertEqual(str(self.vertical), "Test Vertical")

    def test_deactivate_sub_verticals(self):
        """ Verify that deactivating a vertical also deactivates its sub-verticals """
        sub_vertical = SubVerticalFactory(vertical=self.vertical)
        self.assertTrue(sub_vertical.is_active)

        self.vertical.is_active = False
        self.vertical.save()

        sub_vertical.refresh_from_db()
        self.assertFalse(sub_vertical.is_active)


class SubVerticalModelTests(TestCase):

    def setUp(self):
        super().setUp()
        self.vertical = VerticalFactory(name="Technology")
        self.sub_vertical = SubVerticalFactory(
            name="Software Engineering", vertical=self.vertical
        )

    def test_str(self):
        """ Verify the string representation of a sub-vertical """
        self.assertEqual(str(self.sub_vertical), self.sub_vertical.name)

    def test_sub_vertical_filter_creation(self):
        """ Verify that sub-vertical filter is created correctly """
        self.assertEqual(self.sub_vertical.name, "Software Engineering")
        self.assertEqual(self.sub_vertical.vertical, self.vertical)
        self.assertEqual(self.sub_vertical.slug, "software-engineering")
        self.assertTrue(self.sub_vertical.is_active)

    def test_unique_name_constraint(self):
        """ Verify that sub-vertical names must be unique """
        with self.assertRaises(Exception):
            SubVerticalFactory(name="Software Engineering", vertical=self.vertical)


class CourseVerticalModelTests(TestCase):
    def setUp(self):
        self.course_draft = CourseFactory(title="Test Course", draft=True)
        self.course = CourseFactory(title="Test Course", draft=False, draft_version_id=self.course_draft.id)
        self.vertical = VerticalFactory(name="Test Vertical")
        self.sub_vertical = SubVerticalFactory(
            name="Test Sub Vertical", vertical=self.vertical
        )
        self.course_vertical = CourseVerticalFactory(
            course=self.course, vertical=self.vertical, sub_vertical=self.sub_vertical
        )

    def test_course_vertical_filter_creation(self):
        self.assertEqual(self.course_vertical.course, self.course)
        self.assertEqual(self.course_vertical.vertical, self.vertical)
        self.assertEqual(self.course_vertical.sub_vertical, self.sub_vertical)
        self.assertEqual(str(self.course_vertical), "Test Course - Test Vertical - Test Sub Vertical")

    def test_unique_course(self):
        """ Verify that a course can only have one vertical assignment """
        with self.assertRaises(Exception):
            CourseVerticalFactory(
                course=self.course,
                vertical=self.vertical,
                sub_vertical=self.sub_vertical
            )

    def test_cascade_delete_vertical(self):
        """Verify that course verticals are deleted when their vertical is deleted."""
        course_vertical_id = self.course_vertical.id
        self.vertical.delete()

        with self.assertRaises(CourseVertical.DoesNotExist):
            CourseVertical.objects.get(id=course_vertical_id)

    def test_cascade_delete_sub_vertical(self):
        """ Verify that course verticals are deleted when their sub-vertical is deleted """
        course_vertical_id = self.course_vertical.id
        self.sub_vertical.delete()

        with self.assertRaises(CourseVertical.DoesNotExist):
            CourseVertical.objects.get(id=course_vertical_id)

    def test_get_object_title(self):
        """ Verify that get_object_title returns the course title """
        self.assertEqual(self.course_vertical.get_object_title(), self.course.title)

    def test_mismatched_sub_vertical(self):
        """Verify that a sub-vertical must belong to the selected vertical."""
        different_vertical = VerticalFactory()
        mismatched_sub_vertical = SubVerticalFactory(vertical=different_vertical)

        with self.assertRaises(ValidationError):
            CourseVertical.objects.create(
                course=CourseFactory(),
                vertical=self.vertical,
                sub_vertical=mismatched_sub_vertical
            )

    def test_auto_assign_vertical(self):
        """ Verify that vertical is automatically assigned if only sub-vertical is set. """
        course_vertical = CourseVerticalFactory(course=CourseFactory(), sub_vertical=self.sub_vertical, vertical=None)
        self.assertEqual(course_vertical.vertical, self.vertical)
