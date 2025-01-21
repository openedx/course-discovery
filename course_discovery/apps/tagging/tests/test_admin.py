"""
Test the admin interface for the tagging app.
"""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.admin import CourseVerticalAdmin, SubVerticalAdmin, VerticalAdmin
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical
from course_discovery.apps.tagging.tests.factories import CourseVerticalFactory, SubVerticalFactory, VerticalFactory

User = get_user_model()


class MockRequest:
    def __init__(self, user=None):
        self.user = user


class BaseAdminTestCase(TestCase):
    """ Base test class for admin tests """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = AdminSite()

        cls.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password'
        )
        cls.regular_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='password'
        )
        cls.allowed_group = Group.objects.create(name='allowed_group')


class VerticalAdminTests(BaseAdminTestCase):
    """ Tests for VerticalAdmin """

    def setUp(self):
        super().setUp()
        self.vertical_admin = VerticalAdmin(Vertical, self.site)
        self.vertical = VerticalFactory()

    def test_save_model_as_superuser(self):
        """ Verify that superuser can save vertical. """
        request = MockRequest(self.superuser)
        self.vertical.name = 'vertical'
        self.vertical_admin.save_model(request, self.vertical, None, False)
        self.vertical.refresh_from_db()
        self.assertEqual(self.vertical.name, 'vertical')

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save vertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.vertical_admin.save_model(request, self.vertical, None, False)


class SubVerticalAdminTests(BaseAdminTestCase):
    """Tests for SubVerticalAdmin."""

    def setUp(self):
        super().setUp()
        self.subvertical_admin = SubVerticalAdmin(SubVertical, self.site)
        self.subvertical = SubVerticalFactory()

    def test_save_model_as_superuser(self):
        """Verify that superuser can save subvertical."""
        request = MockRequest(self.superuser)
        self.subvertical_admin.save_model(request, self.subvertical, None, False)

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save subvertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.subvertical_admin.save_model(request, self.subvertical, None, False)


class CourseVerticalAdminTests(BaseAdminTestCase):
    """Tests for CourseVerticalAdmin."""

    def setUp(self):
        super().setUp()
        self.coursevertical_admin = CourseVerticalAdmin(CourseVertical, self.site)
        self.course = CourseFactory(draft=False)
        self.vertical = VerticalFactory(is_active=True)
        self.subvertical = SubVerticalFactory(is_active=True, vertical=self.vertical)
        self.coursevertical = CourseVerticalFactory(
            course=self.course,
            vertical=self.vertical,
            sub_vertical=self.subvertical
        )

    def test_save_model_as_superuser(self):
        """Verify that superuser can save course vertical."""
        request = MockRequest(self.superuser)
        self.coursevertical_admin.save_model(request, self.coursevertical, None, False)

    def test_save_model_as_allowed_group_user(self):
        """Verify that user in allowed group can save course vertical."""
        self.regular_user.groups.add(self.allowed_group)
        request = MockRequest(self.regular_user)
        self.coursevertical.sub_vertical = None
        self.coursevertical_admin.save_model(request, self.coursevertical, None, False)
        self.coursevertical.refresh_from_db()
        self.assertIsNone(self.coursevertical.sub_vertical)

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save course vertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.coursevertical_admin.save_model(request, self.coursevertical, None, False)

    def test_formfield_for_foreignkey_vertical(self):
        """ Verify that only active verticals are available """
        inactive_vertical = VerticalFactory(is_active=False)
        request = MockRequest(self.superuser)

        formfield = self.coursevertical_admin.formfield_for_foreignkey(
            CourseVertical._meta.get_field('vertical'),
            request
        )

        self.assertIn(self.vertical, formfield.queryset)
        self.assertNotIn(inactive_vertical, formfield.queryset)

    def test_formfield_for_foreignkey_subvertical(self):
        """Verify that only active subverticals are available."""
        inactive_subvertical = SubVerticalFactory(is_active=False)
        request = MockRequest(self.superuser)

        formfield = self.coursevertical_admin.formfield_for_foreignkey(
            CourseVertical._meta.get_field('sub_vertical'),
            request
        )

        self.assertIn(self.subvertical, formfield.queryset)
        self.assertNotIn(inactive_subvertical, formfield.queryset)
