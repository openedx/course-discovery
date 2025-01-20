from ddt import data, ddt
from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.models import CourseVertical
from course_discovery.apps.tagging.tests.factories import CourseVerticalFactory, SubVerticalFactory, VerticalFactory


class BaseViewsTestCase(TestCase):
    """Base test class for views requiring superuser and VERTICALS_MANAGEMENT_GROUPS permissions."""

    def setUp(self):
        super().setUp()
        self.superuser = UserFactory(is_staff=True, is_superuser=True)
        self.regular_user = UserFactory(is_staff=True, is_superuser=False)

        self.allowed_group = Group.objects.create(name=settings.VERTICALS_MANAGEMENT_GROUPS)

        self.regular_user.groups.add(self.allowed_group)


class CourseTaggingDetailViewTests(BaseViewsTestCase):
    """Tests for the CourseTaggingDetailView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.course = CourseFactory(title="Advanced Python")
        self.vertical = VerticalFactory(name="AI")
        self.sub_vertical = SubVerticalFactory(name="Machine Learning", vertical=self.vertical)
        self.url = reverse("tagging:course_tagging_detail", kwargs={"uuid": self.course.uuid})

    def test_get_course_tagging_detail(self):
        """Tests GET request to course tagging detail view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/course_tagging_detail.html")

    def test_post_valid_vertical_assignment(self):
        """Tests POST request to assign vertical and sub-vertical."""
        mock_response_data = {
            "vertical": self.vertical.slug,
            "sub_vertical": self.sub_vertical.slug,
        }
        response = self.client.post(self.url, data=mock_response_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vertical and Sub-Vertical assigned successfully.")

        course_vertical = CourseVertical.objects.get(course=self.course)
        self.assertEqual(course_vertical.vertical, self.vertical)
        self.assertEqual(course_vertical.sub_vertical, self.sub_vertical)

    def test_post_invalid_sub_vertical(self):
        """Tests POST request with mismatched sub-vertical and vertical."""
        other_vertical = VerticalFactory(name='Business')
        mismatched_sub_vertical = SubVerticalFactory(name='Innovation', vertical=other_vertical)

        mock_response_data = {
            'vertical': self.vertical.slug,
            'sub_vertical': mismatched_sub_vertical.slug,
        }
        response = self.client.post(self.url, data=mock_response_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sub-vertical does not belong to the selected vertical.')


@ddt
class CourseListViewTests(BaseViewsTestCase):
    """Tests for the CourseListView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.course1 = CourseFactory(title="Advanced Python")
        self.course2 = CourseFactory(title="Python Basics")
        self.url = reverse("tagging:course_list")

    def test_get_course_list(self):
        """Tests GET request to course list view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/course_list.html")

    def test_search_course(self):
        """Tests searching for courses in the course list view."""
        response = self.client.get(self.url, {'search': 'Basics'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Basics')
        self.assertNotContains(response, 'Advanced Python')

    @data(('asc', ["Advanced Python", "Python Basics"]), ('desc', ["Python Basics", "Advanced Python"]))
    def test_sort_courses(self, direction_and_order):
        """Tests sorting courses by title in ascending and descending order."""
        direction, expected_order = direction_and_order
        response = self.client.get(self.url, {'sort': 'title', 'direction': direction})
        self.assertEqual(response.status_code, 200)
        courses = response.context['courses']

        self.assertEqual([course.title for course in courses], expected_order)


@ddt
class VerticalListViewTests(BaseViewsTestCase):
    """Tests for the VerticalListView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.vertical1 = VerticalFactory(name="AI")
        self.vertical2 = VerticalFactory(name="Business")
        self.url = reverse("tagging:vertical_list")

    def test_get_vertical_list(self):
        """Tests GET request to vertical list view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/vertical_list.html")

    @data(('asc', ["AI", "Business"]), ('desc', ["Business", "AI"]))
    def test_sort_verticals(self, direction_and_order):
        """Tests sorting verticals by name in descending order."""
        direction, expected_order = direction_and_order
        response = self.client.get(self.url, {'sort': 'name', 'direction': direction})
        self.assertEqual(response.status_code, 200)
        verticals = response.context['verticals']
        self.assertEqual([vertical.name for vertical in verticals], expected_order)


class VerticalDetailViewTests(BaseViewsTestCase):
    """Tests for the VerticalDetailView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.vertical = VerticalFactory(name="AI")
        self.sub_vertical = SubVerticalFactory(name="Python", vertical=self.vertical)
        self.course = CourseFactory(title="Machine Learning")
        _ = CourseVerticalFactory(course=self.course, vertical=self.vertical, sub_vertical=self.sub_vertical)
        self.url = reverse("tagging:vertical_detail", kwargs={"slug": self.vertical.slug})

    def test_get_vertical_detail(self):
        """Tests GET request to vertical detail view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/vertical_detail.html")
        self.assertContains(response, self.vertical.name)
        self.assertContains(response, self.sub_vertical.name)
        self.assertContains(response, self.course.title)


@ddt
class SubVerticalListViewTests(BaseViewsTestCase):
    """Tests for the SubVerticalListView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.vertical = VerticalFactory(name="Technology")
        self.sub_vertical1 = SubVerticalFactory(name="AI", vertical=self.vertical)
        self.sub_vertical2 = SubVerticalFactory(name="Business", vertical=self.vertical)
        self.url = reverse("tagging:sub_vertical_list")

    def test_get_sub_vertical_list(self):
        """Tests GET request to sub-vertical list view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/sub_vertical_list.html")
        self.assertIn("sub_verticals", response.context)

    @data(('asc', ["AI", "Business"]), ('desc', ["Business", "AI"]))
    def test_sort_sub_verticals(self, direction_and_order):
        """Tests sorting sub-verticals by name in ascending and descending order."""
        direction, expected_order = direction_and_order
        response = self.client.get(self.url, {"sort": "name", "direction": direction})
        self.assertEqual(response.status_code, 200)
        sub_verticals = response.context["sub_verticals"]
        self.assertEqual([sub_vertical.name for sub_vertical in sub_verticals], expected_order)


class SubVerticalDetailViewTests(BaseViewsTestCase):
    """Tests for the SubVerticalDetailView."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.superuser)
        self.vertical = VerticalFactory(name="AI")
        self.sub_vertical = SubVerticalFactory(name="Python", vertical=self.vertical)
        self.course = CourseFactory(title="Deep Learning")
        _ = CourseVerticalFactory(course=self.course, vertical=self.vertical, sub_vertical=self.sub_vertical)
        self.url = reverse("tagging:sub_vertical_detail", kwargs={"slug": self.sub_vertical.slug})

    def test_get_sub_vertical_detail(self):
        """Tests GET request to sub-vertical detail view."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tagging/sub_vertical_detail.html")
        self.assertContains(response, self.sub_vertical.name)
        self.assertContains(response, self.vertical.name)
        self.assertContains(response, self.course.title)
