"""
Test the admin interface for the tagging app.
"""
from django.conf import settings
from django.contrib.admin.sites import AdminSite, site
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

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

    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.factory = RequestFactory()

        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password'
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='password'
        )

        self.allowed_group = Group.objects.create(name='allowed_group')
        settings.VERTICALS_MANAGEMENT_GROUPS = ['allowed_group']


class VerticalAdminTests(BaseAdminTestCase):
    """ Tests for VerticalAdmin """

    def setUp(self):
        super().setUp()
        self.vertical_admin = VerticalAdmin(Vertical, self.site)
        self.vertical = VerticalFactory()

    def test_save_model_as_superuser(self):
        """Verify that superuser can save vertical."""
        request = MockRequest(self.superuser)
        try:
            self.vertical_admin.save_model(request, self.vertical, None, False)
        except PermissionDenied:
            self.fail("Superuser should be able to save vertical")

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save vertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.vertical_admin.save_model(request, self.vertical, None, False)

    def test_list_display(self):
        """Verify the correct list display fields."""
        self.assertEqual(
            self.vertical_admin.list_display,
            ('name', 'is_active', 'slug',)
        )

    def test_vertical_filter_admin_registration(self):
        """ Verify that Vertical model is registered on the admin site """
        self.assertIn(Vertical, site._registry)


class SubVerticalAdminTests(BaseAdminTestCase):
    """Tests for SubVerticalAdmin."""

    def setUp(self):
        super().setUp()
        self.subvertical_admin = SubVerticalAdmin(SubVertical, self.site)
        self.subvertical = SubVerticalFactory()

    def test_save_model_as_superuser(self):
        """Verify that superuser can save subvertical."""
        request = MockRequest(self.superuser)
        try:
            self.subvertical_admin.save_model(request, self.subvertical, None, False)
        except PermissionDenied:
            self.fail("Superuser should be able to save subvertical")

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save subvertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.subvertical_admin.save_model(request, self.subvertical, None, False)

    def test_list_display(self):
        """Verify the correct list display fields."""
        self.assertEqual(
            self.subvertical_admin.list_display,
            ('name', 'is_active', 'slug', 'verticals')
        )

    def test_sub_vertical_filter_admin_registration(self):
        """Verify that SubVertical model is registered on the admin site."""
        self.assertIn(SubVertical, site._registry)


class CourseVerticalAdminTests(BaseAdminTestCase):
    """Tests for CourseVerticalAdmin."""

    def setUp(self):
        super().setUp()
        self.coursevertical_admin = CourseVerticalAdmin(CourseVertical, self.site)
        self.course = CourseFactory(draft=False)
        self.vertical = VerticalFactory(is_active=True)
        self.subvertical = SubVerticalFactory(is_active=True, verticals=self.vertical)
        self.coursevertical = CourseVerticalFactory(
            course=self.course,
            vertical=self.vertical,
            sub_vertical=self.subvertical
        )

    def test_save_model_as_superuser(self):
        """Verify that superuser can save course vertical."""
        request = MockRequest(self.superuser)
        try:
            self.coursevertical_admin.save_model(request, self.coursevertical, None, False)
        except PermissionDenied:
            self.fail("Superuser should be able to save course vertical")

    def test_save_model_as_allowed_group_user(self):
        """Verify that user in allowed group can save course vertical."""
        self.regular_user.groups.add(self.allowed_group)
        request = MockRequest(self.regular_user)
        try:
            self.coursevertical_admin.save_model(request, self.coursevertical, None, False)
        except PermissionDenied:
            self.fail("User in allowed group should be able to save course vertical")

    def test_save_model_as_regular_user(self):
        """Verify that regular user cannot save course vertical."""
        request = MockRequest(self.regular_user)
        with self.assertRaises(PermissionDenied):
            self.coursevertical_admin.save_model(request, self.coursevertical, None, False)

    def test_formfield_for_foreignkey_course(self):
        """Verify that only non-draft courses are available."""
        draft_course = CourseFactory(draft=True)
        request = MockRequest(self.superuser)

        formfield = self.coursevertical_admin.formfield_for_foreignkey(
            CourseVertical._meta.get_field('course'),
            request
        )

        self.assertIn(self.course, formfield.queryset)
        self.assertNotIn(draft_course, formfield.queryset)

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

    def test_list_display(self):
        """Verify the correct list display fields."""
        self.assertEqual(
            self.coursevertical_admin.list_display,
            ('course', 'vertical', 'sub_vertical')
        )

    def test_course_vertical_filter_admin_registration(self):
        """ Verify that CourseVertical model is registered on the admin site """
        self.assertIn(CourseVertical, site._registry)
