"""
Test the admin interface for the tagging app.
"""
from django.contrib.admin.sites import site
from django.test import RequestFactory, TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.admin import CourseVerticalAdmin
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical
from course_discovery.apps.tagging.tests.factories import SubVerticalFactory, VerticalFactory


class AdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.active_vertical = VerticalFactory(name="Technology", is_active=True)
        self.inactive_vertical = VerticalFactory(
            name="Inactive Vertical", is_active=False
        )

        self.active_sub_vertical = SubVerticalFactory(
            name="Software Engineering",
            verticals=self.active_vertical,
            is_active=True,
        )
        self.inactive_sub_vertical = SubVerticalFactory(
            name="Inactive SubVertical",
            verticals=self.active_vertical,
            is_active=False,
        )

        self.non_draft_course = CourseFactory(title="Try Course", draft=False)
        self.draft_course = CourseFactory(title="Draft Try Course", draft=True)

    def test_vertical_filter_admin_registration(self):
        self.assertIn(Vertical, site._registry)

    def test_sub_vertical_filter_admin_registration(self):
        self.assertIn(SubVertical, site._registry)

    def test_course_vertical_filter_admin_registration(self):
        self.assertIn(CourseVertical, site._registry)

    def test_formfield_for_foreignkey_filters_active_verticals(self):
        admin_instance = CourseVerticalAdmin(CourseVertical, site)
        request = self.factory.get("/admin/")

        formfield = admin_instance.formfield_for_foreignkey(
            db_field=CourseVertical._meta.get_field("vertical"), request=request
        )
        queryset = formfield.queryset

        self.assertIn(self.active_vertical, queryset)
        self.assertNotIn(self.inactive_vertical, queryset)

    def test_formfield_for_foreignkey_filters_active_sub_verticals(self):
        admin_instance = CourseVerticalAdmin(CourseVertical, site)
        request = self.factory.get("/admin/")

        formfield = admin_instance.formfield_for_foreignkey(
            db_field=CourseVertical._meta.get_field("sub_vertical"),
            request=request,
        )
        queryset = formfield.queryset

        self.assertIn(self.active_sub_vertical, queryset)
        self.assertNotIn(self.inactive_sub_vertical, queryset)

    def test_formfield_for_foreignkey_filters_non_draft_courses(self):
        admin_instance = CourseVerticalAdmin(CourseVertical, site)
        request = self.factory.get("/admin/")

        formfield = admin_instance.formfield_for_foreignkey(
            db_field=CourseVertical._meta.get_field("course"), request=request
        )
        queryset = formfield.queryset

        self.assertIn(self.non_draft_course, queryset)
        self.assertNotIn(self.draft_course, queryset)
