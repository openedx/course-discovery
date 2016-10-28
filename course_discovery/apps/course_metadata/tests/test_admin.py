import itertools

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase, LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.forms import ProgramAdminForm
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests import factories


# pylint: disable=no-member
@ddt.ddt
class AdminTests(TestCase):
    """ Tests Admin page."""

    def setUp(self):
        super(AdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_runs = factories.CourseRunFactory.create_batch(3)
        self.courses = [course_run.course for course_run in self.course_runs]

        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(
            courses=self.courses, excluded_course_runs=[self.excluded_course_run]
        )

    def _post_data(self, status=ProgramStatus.Unpublished, marketing_slug='/foo'):
        return {
            'title': 'some test title',
            'courses': [self.courses[0].id],
            'type': self.program.type.id,
            'status': status,
            'marketing_slug': marketing_slug,
            'partner': self.program.partner.id
        }

    def assert_form_valid(self, data, files):
        form = ProgramAdminForm(data=data, files=files)
        self.assertTrue(form.is_valid())
        program = form.save()
        response = self.client.get(reverse('admin:course_metadata_program_change', args=(program.id,)))
        self.assertEqual(response.status_code, 200)

    def assert_form_invalid(self, data, files):
        form = ProgramAdminForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['__all__'],
            ['Programs can only be activated if they have a marketing slug and a banner image.']
        )
        with self.assertRaises(ValueError):
            form.save()

    def test_program_detail_form(self):
        """ Verify in admin panel program detail form load successfully. """
        response = self.client.get(reverse('admin:course_metadata_program_change', args=(self.program.id,)))
        self.assertEqual(response.status_code, 200)

    def test_custom_course_selection_page(self):
        """ Verify that course selection page loads successfully. """
        response = self.client.get(reverse('admin_metadata:update_course_runs', args=(self.program.id,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('admin:course_metadata_program_change', args=(self.program.id,)))
        self.assertContains(response, reverse('admin:course_metadata_program_changelist'))

    def test_custom_course_selection_page_with_invalid_id(self):
        """ Verify that course selection page will return 404 for invalid program id. """
        response = self.client.get(reverse('admin_metadata:update_course_runs', args=(10,)))
        self.assertEqual(response.status_code, 404)

    def test_custom_course_selection_page_with_non_staff(self):
        """ Verify that course selection page will return 404 for non authorized user. """
        self.client.logout()
        self.user.is_superuser = False
        self.user.is_staff = False
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        response = self.client.get(reverse('admin_metadata:update_course_runs', args=(self.program.id,)))
        self.assertEqual(response.status_code, 404)

    def test_page_loads_only_course_related_runs(self):
        """ Verify that course selection page loads only all course runs. Also marked checkboxes with
        excluded courses runs only.
        """
        # add some new courses and course runs
        factories.CourseRunFactory.create_batch(2)
        response = self.client.get(reverse('admin_metadata:update_course_runs', args=(self.program.id,)))
        html = '<input checked="checked" id="id_excluded_course_runs_0" '
        html += 'name="excluded_course_runs" type="checkbox" value="{id}" />'.format(
            id=self.excluded_course_run.id
        )
        self.assertContains(response, html)
        for run in self.course_runs:
            self.assertContains(response, run.key)

    def test_page_with_post_new_course_run(self):
        """ Verify that course selection page with posting the data. """

        self.assertEqual(1, self.program.excluded_course_runs.all().count())
        self.assertEqual(3, sum(1 for _ in self.program.course_runs))

        params = {
            'excluded_course_runs': [self.excluded_course_run.id, self.course_runs[0].id],
        }
        post_url = reverse('admin_metadata:update_course_runs', args=(self.program.id,))
        response = self.client.post(post_url, params)
        self.assertRedirects(
            response,
            expected_url=reverse('admin:course_metadata_program_change', args=(self.program.id,)),
            status_code=302,
            target_status_code=200
        )
        self.assertEqual(2, self.program.excluded_course_runs.all().count())
        self.assertEqual(2, sum(1 for _ in self.program.course_runs))

    def test_page_with_post_without_course_run(self):
        """ Verify that course selection page without posting any selected excluded check run. """

        self.assertEqual(1, self.program.excluded_course_runs.all().count())
        params = {
            'excluded_course_runs': [],
        }
        post_url = reverse('admin_metadata:update_course_runs', args=(self.program.id,))
        response = self.client.post(post_url, params)
        self.assertRedirects(
            response,
            expected_url=reverse('admin:course_metadata_program_change', args=(self.program.id,)),
            status_code=302,
            target_status_code=200
        )
        self.assertEqual(0, self.program.excluded_course_runs.all().count())
        self.assertEqual(4, sum(1 for _ in self.program.course_runs))
        response = self.client.get(reverse('admin_metadata:update_course_runs', args=(self.program.id,)))
        self.assertNotContains(response, '<input checked="checked")')

    @ddt.data(
        *itertools.product(
            (
                (False, False, False),
                (True, False, False),
                (False, True, False),
                (True, True, True)
            ),
            ProgramStatus.labels
        )
    )
    @ddt.unpack
    def test_program_activation_restrictions(self, booleans, label):
        """Verify that program activation requires both a marketing slug and a banner image."""
        has_marketing_slug, has_banner_image, can_be_activated = booleans
        status = getattr(ProgramStatus, label)

        marketing_slug = '/foo' if has_marketing_slug else ''
        banner_image = make_image_file('test_banner.jpg') if has_banner_image else ''

        data = self._post_data(status=status, marketing_slug=marketing_slug)
        files = {'banner_image': banner_image}

        if status == ProgramStatus.Active:
            if can_be_activated:
                # Transitioning to an active status should require a marketing slug and banner image.
                self.assert_form_valid(data, files)
            else:
                self.assert_form_invalid(data, files)
        else:
            # All other status transitions should be valid regardless of marketing slug and banner image.
            self.assert_form_valid(data, files)

    def test_new_program_without_courses(self):
        """ Verify that new program can be added without `courses`."""
        data = self._post_data()
        data['courses'] = []
        form = ProgramAdminForm(data)
        self.assertTrue(form.is_valid())
        program = form.save()
        self.assertEqual(0, program.courses.all().count())
        response = self.client.get(reverse('admin:course_metadata_program_change', args=(program.id,)))
        self.assertEqual(response.status_code, 200)


class ProgramAdminFunctionalTests(LiveServerTestCase):
    """ Functional Tests for Admin page."""
    create_view_name = 'admin:course_metadata_program_add'
    edit_view_name = 'admin:course_metadata_program_change'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.browser = webdriver.PhantomJS()
        cls.browser.implicitly_wait(10)
        cls.browser.set_window_size(1024, 768)

        cls.user = UserFactory(is_staff=True, is_superuser=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    @classmethod
    def _submit_form(cls):
        cls.browser.find_element_by_css_selector('input[type=submit]').click()

    @classmethod
    def _login(cls):
        """ Log into Django admin. """
        cls.browser.get(cls._build_url(reverse('admin:login')))
        cls.browser.find_element_by_id('id_username').send_keys(cls.user.username)
        cls.browser.find_element_by_id('id_password').send_keys(USER_PASSWORD)
        cls._submit_form()

    @classmethod
    def _build_url(cls, path):
        """ Returns a URL for the live test server. """
        return cls.live_server_url + path

    def setUp(self):
        super().setUp()

        self.course_runs = factories.CourseRunFactory.create_batch(2)
        self.courses = [course_run.course for course_run in self.course_runs]

        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(
            courses=self.courses, excluded_course_runs=[self.excluded_course_run]
        )

        # NOTE (CCB): We must login for every test. Cookies don't seem to be persisted across test cases.
        self._login()

    def _navigate_to_edit_page(self):
        url = self._build_url(reverse(self.edit_view_name, args=(self.program.id,)))
        self.browser.get(url)

    def _select_option(self, select_id, option_value):
        select = self.browser.find_element_by_id(select_id)
        select.select_by_value(option_value)

    def test_all_fields(self):
        """ Verify the expected fields are present on the program admin page. """
        self._navigate_to_edit_page()

        fields = (
            'title', 'subtitle', 'status', 'type', 'partner', 'banner_image', 'banner_image_url', 'card_image_url',
            'marketing_slug', 'overview', 'credit_redemption_overview', 'video', 'weeks_to_complete',
            'min_hours_effort_per_week', 'max_hours_effort_per_week', 'courses', 'order_courses_by_start_date',
            'authoring_organizations', 'credit_backing_organizations', 'job_outlook_items', 'expected_learning_items',
        )
        for field in fields:
            self.browser.find_element_by_id('id_' + field)

        m2m_fields = ('id_Program_faq-0-faq', 'id_Program_individual_endorsements-0-endorsement',
                      'id_Program_corporate_endorsements-0-corporateendorsement',)
        for field in m2m_fields:
            self.browser.find_element_by_id(field)

    def test_sortable_select_drag_and_drop(self):
        """ Verify the program admin page allows for dragging and dropping courses. """
        self._navigate_to_edit_page()

        # Get order of select elements
        hidden_options_text = [el.text for el in
                               self.browser.find_elements_by_css_selector('.field-courses option')]
        first_select_element = self.browser.find_element_by_css_selector('.field-courses .select2-selection__choice')

        # Drag and drop
        first_select_element.click()
        ActionChains(self.browser).drag_and_drop_by_offset(first_select_element, 500, 0).perform()

        # Simulate expected drag and drop
        hidden_options_text = [hidden_options_text[1], hidden_options_text[0]]

        # Get actual results of drag and drop
        new_hidden_options_text = [el.text for el in
                                   self.browser.find_elements_by_css_selector('.field-courses option')]
        self.assertEqual(hidden_options_text, new_hidden_options_text)

    def test_program_creation(self):
        url = self._build_url(reverse(self.create_view_name))
        program = factories.ProgramFactory.build(partner=Partner.objects.first(), status=ProgramStatus.Unpublished)

        self.browser.get(url)
        self.browser.find_element_by_id('id_title').send_keys(program.title)
        self.browser.find_element_by_id('id_subtitle').send_keys(program.subtitle)
        self._select_option('id_status', program.status.id)
        self._select_option('id_type', program.type.id)
        self._select_option('id_partner', program.partner.id)
        self._submit_form()

        actual = Program.objects.latest()
        self.assertEqual(actual.title, program.title)
        self.assertEqual(actual.subtitle, program.subtitle)
        self.assertEqual(actual.status, program.status)
        self.assertEqual(actual.type, program.type)
        self.assertEqual(actual.partner, program.partner)

    def test_program_update(self):
        self._navigate_to_edit_page()

        title = 'Test Program'
        subtitle = 'This is a test.'

        # Update the program
        self.browser.find_element_by_id('id_title').send_keys(title)
        self.browser.find_element_by_id('id_subtitle').send_keys(subtitle)
        self._submit_form()

        # Verify the program was updated
        self.program = Program.objects.get(pk=self.program.pk)
        self.assertEqual(self.program.title, title)
        self.assertEqual(self.program.subtitle, subtitle)
