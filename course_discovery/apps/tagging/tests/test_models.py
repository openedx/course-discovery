"""
Tests for the models registered in tagging app
"""
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.tests.factories import (
    CourseVerticalFactory, SubVerticalFactory, VerticalFactory
)


class VerticalFilterModelTests(TestCase):
    def setUp(self):
        self.vertical = VerticalFactory(name="Test Vertical", is_active=True)

    def test_vertical_filter_creation(self):
        self.assertEqual(self.vertical.name, "Test Vertical")
        self.assertTrue(self.vertical.is_active)
        self.assertTrue(self.vertical.slug == "test-vertical")
        self.assertEqual(str(self.vertical), "Test Vertical")

    def test_unique_name_constraint(self):
        with self.assertRaises(Exception):
            VerticalFactory(name="Test Vertical")


class SubVerticalFilterModelTests(TestCase):

    def setUp(self):
        self.vertical = VerticalFactory(name="Technology")
        self.sub_vertical = SubVerticalFactory(
            name="Software Engineering", verticals=self.vertical
        )

    def test_sub_vertical_filter_creation(self):
        self.assertEqual(self.sub_vertical.name, "Software Engineering")
        self.assertEqual(self.sub_vertical.verticals, self.vertical)
        self.assertTrue(self.sub_vertical.slug == "software-engineering")
        self.assertTrue(self.sub_vertical.is_active)

    def test_unique_name_constraint(self):
        with self.assertRaises(Exception):
            SubVerticalFactory(name="Software Engineering", verticals=self.vertical)


class CourseVerticalFilterModelTests(TestCase):
    def setUp(self):
        self.course_draft = CourseFactory(title="Test Course", draft=True)
        self.course = CourseFactory(title="Test Course", draft=False, draft_version_id=self.course_draft.id)
        self.vertical = VerticalFactory(name="Test Vertical")
        self.sub_vertical = SubVerticalFactory(
            name="Test Sub Vertical", verticals=self.vertical
        )
        self.course_vertical = CourseVerticalFactory(
            course=self.course, vertical=self.vertical, sub_vertical=self.sub_vertical
        )

    def test_course_vertical_filter_creation(self):
        self.assertEqual(self.course_vertical.course, self.course)
        self.assertEqual(self.course_vertical.vertical, self.vertical)
        self.assertEqual(self.course_vertical.sub_vertical, self.sub_vertical)
        self.assertEqual(str(self.course_vertical), "Test Course - Test Vertical - Test Sub Vertical")
