from ddt import data, ddt
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.test import LiveServerTestCase, TestCase
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait

from course_discovery.apps.api.tests.mixins import SiteMixin
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
        self.assertContains(response, "Course Vertical added successfully.")

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


class CourseTaggingDetailViewJSTests(SiteMixin, LiveServerTestCase):
    """
    Functional tests using Selenium to verify the JS script filterSubVerticals behavior in the CourseTaggingDetailView.
    """

    def tearDown(self):
        """Clean up all created objects to avoid ProtectedError on deletion."""
        from course_discovery.apps.tagging.models import CourseVertical, SubVertical, Vertical
        from course_discovery.apps.course_metadata.models import Course

        # Delete CourseVerticals first (depends on Course, Vertical, SubVertical)
        CourseVertical.objects.all().delete()
        # Delete SubVerticals and Verticals
        SubVertical.objects.all().delete()
        Vertical.objects.all().delete()
        # Delete Courses
        Course.objects.all().delete()
        super().tearDown()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        firefox_options = Options()
        # firefox_options.headless = True
        firefox_options.add_argument('--headless')
        cls.driver = webdriver.Firefox(options=firefox_options)
        cls.driver.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def _wait_for_page_load(self, timeout=10):
        """Wait until the page's document.readyState is 'complete'."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def setUp(self):
        """
        Create a superuser, a course, verticals and sub-verticals used for testing.
        """
        super().setUp()
        ContentType.objects.clear_cache()

        self.user = UserFactory(username='superuser', is_superuser=True, is_staff=True)
        self.user.set_password('password')
        self.user.save()

        self.course = CourseFactory(title='Advanced Python')

        self.vertical = VerticalFactory(name='vertical')
        self.sub_vertical = SubVerticalFactory(name='sub_vertical', vertical=self.vertical)

        self.other_vertical = VerticalFactory(name='other_vertical')
        self.other_sub_vertical = SubVerticalFactory(name='other_sub_vertical', vertical=self.other_vertical)

        self.multi_vertical = VerticalFactory(name='multi_vertical')
        self.multi_sub_vertical1 = SubVerticalFactory(name='multi_sub_vertical1', vertical=self.multi_vertical)
        self.multi_sub_vertical2 = SubVerticalFactory(name='multi_sub_vertical2', vertical=self.multi_vertical)

        _ = CourseVerticalFactory(course=self.course, vertical=self.vertical, sub_vertical=self.sub_vertical)

        self.url = self.live_server_url + reverse('tagging:course_tagging_detail', kwargs={'uuid': self.course.uuid})

        self._login()

        self.driver.get(self.url)
        self._wait_for_page_load()

    def _login(self):
        """Log into Django via test client, then add the session cookie to Selenium."""
        self.client.force_login(self.user)
        session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.driver.get(self.live_server_url)
        cookie_dict = {
            'name': settings.SESSION_COOKIE_NAME,
            'value': session_cookie.value,
            'path': '/',
        }
        self.driver.add_cookie(cookie_dict)
        self.driver.get(self.url)
        self._wait_for_page_load()

    def get_visible_options(self, select_id):
        """
        Returns a list of visible <option> elements for the given select element.
        Visible options are defined as those with a 'data-vertical' attribute and no inline 'display: none' style.
        """
        select_element = self.driver.find_element(By.ID, select_id)
        options = select_element.find_elements(By.TAG_NAME, 'option')
        visible_options = [
            option for option in options
            if option.get_attribute('data-vertical') is not None and
            'display: none' not in (option.get_attribute('style') or '')
        ]
        return visible_options

    def filter_sub_verticals(self, vertical_slug, expected_slugs):
        """
        Selects the vertical with the given slug, triggers the JavaScript change event, and waits
        until the expected sub-vertical options (by their slug values) are visible in the sub_vertical select.
        Returns the list of visible option elements.
        """
        vertical_select = Select(self.driver.find_element(By.ID, 'vertical'))
        vertical_select.select_by_value(vertical_slug)
        self.driver.execute_script(
            "document.getElementById('vertical').dispatchEvent(new Event('change'));"
        )
        visible_options = self.get_visible_options('sub_vertical')
        WebDriverWait(self.driver, 10).until(
            lambda d: set(
                option.get_attribute('value')
                for option in visible_options
            ) == set(expected_slugs)
        )
        return visible_options

    def test_initial_load(self):
        """
        Test that on initial load (before any user interaction), the course displays the pre-assigned vertical
        and sub-vertical. Additionally, verify that the sub-vertical dropdown only contains options associated
        with the selected vertical.
        """
        vertical_select = Select(self.driver.find_element(By.ID, 'vertical'))
        selected_vertical = vertical_select.first_selected_option.get_attribute('value')
        self.assertEqual(selected_vertical, self.vertical.slug)

        sub_vertical_select = Select(self.driver.find_element(By.ID, 'sub_vertical'))
        selected_sub_vertical = sub_vertical_select.first_selected_option.get_attribute('value')
        self.assertEqual(selected_sub_vertical, self.sub_vertical.slug)

        visible_options = self.get_visible_options('sub_vertical')

        expected_options = {self.sub_vertical.slug}
        actual_options = {option.get_attribute('value') for option in visible_options}
        self.assertEqual(actual_options, expected_options)

    def test_filter_sub_verticals_javascript(self):
        """
        Verify that selecting a vertical with one sub-vertical shows the expected single sub-vertical
        and a vertical with two sub-verticals shows both sub-verticals.
        """
        visible_options = self.filter_sub_verticals(self.vertical.slug, [self.sub_vertical.slug])
        self.assertEqual(len(visible_options), 1)
        self.assertEqual(visible_options[0].get_attribute('value'), self.sub_vertical.slug)

        visible_options = self.filter_sub_verticals(self.other_vertical.slug, [self.other_sub_vertical.slug])
        self.assertEqual(len(visible_options), 1)
        self.assertEqual(visible_options[0].get_attribute('value'), self.other_sub_vertical.slug)

        visible_options = self.filter_sub_verticals(
            self.multi_vertical.slug,
            [self.multi_sub_vertical1.slug, self.multi_sub_vertical2.slug]
        )
        option_values = sorted([option.get_attribute('value') for option in visible_options])
        expected_values = sorted([self.multi_sub_vertical1.slug, self.multi_sub_vertical2.slug])
        self.assertEqual(len(visible_options), 2)
        self.assertEqual(option_values, expected_values)


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
