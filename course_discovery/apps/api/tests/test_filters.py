from django.test import TestCase
from mock import MagicMock
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from course_discovery.apps.api.filters import CourseFilter, HaystackRequestFilterMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseEditorFactory, CourseFactory
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


class TestHaystackRequestFilterMixin:
    def test_get_request_filters(self):
        """ Verify the method removes query parameters with empty values """
        request = APIRequestFactory().get('/?q=')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert filters == {}

    def test_get_request_filters_with_list(self):
        """ Verify the method does not affect list values. """
        request = APIRequestFactory().get('/?q=&content_type=courserun&content_type=program')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert 'q' not in filters
        assert filters.getlist('content_type') == ['courserun', 'program']

    def test_get_request_filters_with_falsey_values(self):
        """ Verify the method does not strip valid falsey values. """
        request = APIRequestFactory().get('/?q=&test=0')
        request = APIView().initialize_request(request)
        filters = HaystackRequestFilterMixin.get_request_filters(request)
        assert 'q' not in filters
        assert filters.get('test') == '0'


class TestCourseFilter(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.qs = Course.objects.all()

        self.org_ext = OrganizationExtensionFactory()
        self.user.groups.add(self.org_ext.group)

        # *** Add a bunch of courses ***

        # Course with no editors
        self.course_no_editors = CourseFactory(title="no editors")

        # Course with an invalid editor (no group membership)
        bad_editor = UserFactory()
        self.course_bad_editor = CourseFactory(title="bad editor")
        CourseEditorFactory(user=bad_editor, course=self.course_bad_editor)

        # Course with an invalid editor (but course is in our group)
        self.course_bad_editor_in_group = CourseFactory(title="bad editor in group")
        self.course_bad_editor_in_group.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        CourseEditorFactory(user=bad_editor, course=self.course_bad_editor_in_group)

        # Course with a valid other editor
        good_editor = UserFactory()
        good_editor.groups.add(self.org_ext.group)
        self.course_good_editor = CourseFactory(title="good editor")
        self.course_good_editor.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        CourseEditorFactory(user=good_editor, course=self.course_good_editor)

        # Course with user as an invalid editor (no group membership)
        self.course_no_group = CourseFactory(title="no group")
        CourseEditorFactory(user=self.user, course=self.course_no_group)

        # Course with user as an valid editor
        self.course_editor = CourseFactory(title="editor")
        self.course_editor.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        CourseEditorFactory(user=self.user, course=self.course_editor)

        # *** End course definitions ***

        request = MagicMock()
        request.user = self.user
        self.filter = CourseFilter(request=request)

    def filter_editable(self, value='1'):
        return self.filter.filter_editable(self.qs, 'editable', value)

    def test_editable_no_request(self):
        """ Verify the we don't touch the queryset if no request is passed. """
        self.filter = CourseFilter()
        with self.assertNumQueries(0):
            self.assertEqual(self.filter_editable(), self.qs)

    def test_editable_disabled(self):
        """ Verify the we don't touch the queryset if editable is off. """
        with self.assertNumQueries(0):
            self.assertEqual(self.filter_editable('0'), self.qs)

    def test_editable_is_staff(self):
        """ Verify staff users can see all courses. """
        self.user.is_staff = True
        self.user.save()
        with self.assertNumQueries(0):
            self.assertEqual(self.filter_editable(), self.qs)

    def test_editable_no_access(self):
        """ Verify users without any editor status see nothing. """
        self.user.groups.clear()
        self.assertEqual(list(self.filter_editable()), [])

    def test_editable(self):
        """ Verify users can see courses they can edit. """
        with self.assertNumQueries(1):
            self.assertEqual(list(self.filter_editable()), [self.course_bad_editor_in_group, self.course_editor])
