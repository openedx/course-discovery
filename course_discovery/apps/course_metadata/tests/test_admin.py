import itertools

import ddt
from bs4 import BeautifulSoup
from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.test import LiveServerTestCase, TestCase
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import USER_PASSWORD, PartnerFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.admin import PositionAdmin, ProgramEligibilityFilter
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.constants import PathwayType
from course_discovery.apps.course_metadata.forms import PathwayAdminForm, ProgramAdminForm
from course_discovery.apps.course_metadata.models import Person, Position, Program, ProgramType
from course_discovery.apps.course_metadata.tests import factories


# pylint: disable=no-member
@ddt.ddt
class AdminTests(SiteMixin, TestCase):
    """ Tests Admin page."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = UserFactory(is_staff=True, is_superuser=True)
        cls.course_runs = factories.CourseRunFactory.create_batch(3)
        cls.courses = [course_run.course for course_run in cls.course_runs]

        cls.excluded_course_run = factories.CourseRunFactory(course=cls.courses[0])
        cls.program = factories.ProgramFactory(
            courses=cls.courses,
            excluded_course_runs=[cls.excluded_course_run],
            partner=cls.partner,  # cls.partner provided by SiteMixin.setUpClass()
        )

    def setUp(self):
        super().setUp()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

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
            ['Programs can only be activated if they have a banner image.']
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
        response_content = BeautifulSoup(response.content)
        attribute = response_content.find(
            "input", {"value": self.excluded_course_run.id, "type": "checkbox", "name": "excluded_course_runs"}
        )
        assert attribute is not None

        for run in self.course_runs:
            self.assertContains(response, run.key)

    def test_updating_order_of_authoring_orgs(self):
        org1 = factories.OrganizationFactory(key='org1')
        org2 = factories.OrganizationFactory(key='org2')
        org3 = factories.OrganizationFactory(key='org3')

        course = factories.CourseFactory(authoring_organizations=[org1, org2, org3])

        new_ordering = (',').join(map(lambda org: str(org.id), [org2, org3, org1]))
        params = {'authoring_organizations': new_ordering}

        post_url = reverse('admin:course_metadata_course_change', args=(course.id,))
        response = self.client.post(post_url, params)
        self.assertEqual(response.status_code, 200)

        html = BeautifulSoup(response.content)

        orgs_dropdown_text = html.find(class_='field-authoring_organizations').get_text()

        self.assertLess(orgs_dropdown_text.index('org2'), orgs_dropdown_text.index('org3'))
        self.assertLess(orgs_dropdown_text.index('org3'), orgs_dropdown_text.index('org1'))

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
                (False, False),
                (True, True)
            ),
            sorted(ProgramStatus.labels)  # We need a consistent ordering to distribute tests with pytest-xdist
        )
    )
    @ddt.unpack
    def test_program_activation_restrictions(self, booleans, label):
        """Verify that program activation requires both a marketing slug and a banner image."""
        has_banner_image, can_be_activated = booleans
        status = getattr(ProgramStatus, label)

        banner_image = make_image_file('test_banner.jpg') if has_banner_image else ''

        data = self._post_data(status=status, marketing_slug='/foo')
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


class ProgramAdminFunctionalTests(SiteMixin, LiveServerTestCase):
    """ Functional Tests for Admin page."""
    # Required for access to initial data loaded in migrations (e.g., LanguageTags).
    serialized_rollback = True

    create_view_name = 'admin:course_metadata_program_add'
    edit_view_name = 'admin:course_metadata_program_change'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opts = Options()
        opts.set_headless()
        cls.browser = webdriver.Firefox(options=opts)
        cls.browser.set_window_size(1024, 768)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    @classmethod
    def _build_url(cls, path):
        """ Returns a URL for the live test server. """
        return cls.live_server_url + path

    @classmethod
    def _wait_for_page_load(cls, body_class):
        """ Wait for the page to load. """
        WebDriverWait(cls.browser, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'body.' + body_class))
        )

    def setUp(self):
        super().setUp()
        # ContentTypeManager uses a cache to speed up ContentType retrieval. This
        # cache persists across tests. This is fine in the context of a regular
        # TestCase which uses a transaction to reset the database between tests.
        # However, it becomes a problem in subclasses of TransactionTestCase which
        # truncate all tables to reset the database between tests. When tables are
        # truncated, ContentType objects in the ContentTypeManager's cache become
        # stale. Attempting to use these stale objects in tests such as the ones
        # below, which create LogEntry objects as a side-effect of interacting with
        # the admin, will result in IntegrityErrors on databases that check foreign
        # key constraints (e.g., MySQL). Preemptively clearing the cache prevents
        # stale ContentType objects from being used.
        ContentType.objects.clear_cache()

        self.site.domain = self.live_server_url.strip('http://')
        self.site.save()

        self.course_runs = factories.CourseRunFactory.create_batch(2)
        self.courses = [course_run.course for course_run in self.course_runs]

        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(
            courses=self.courses, excluded_course_runs=[self.excluded_course_run], status=ProgramStatus.Unpublished
        )

        self.user = UserFactory(is_staff=True, is_superuser=True)
        self._login()

    def _login(self):
        """ Log into Django admin. """
        self.browser.get(self._build_url(reverse('admin:login')))
        self.browser.find_element_by_id('id_username').send_keys(self.user.username)
        self.browser.find_element_by_id('id_password').send_keys(USER_PASSWORD)
        self.browser.find_element_by_css_selector('input[type=submit]').click()
        self._wait_for_page_load('dashboard')

    def _wait_for_add_edit_page_to_load(self):
        self._wait_for_page_load('change-form')

    def _wait_for_excluded_course_runs_page_to_load(self):
        self._wait_for_page_load('change-program-excluded-course-runs-form')

    def _navigate_to_edit_page(self):
        url = self._build_url(reverse(self.edit_view_name, args=(self.program.id,)))
        self.browser.get(url)
        self._wait_for_add_edit_page_to_load()

    def _select_option(self, select_id, option_value):
        select = Select(self.browser.find_element_by_id(select_id))
        select.select_by_value(option_value)

    def _submit_program_form(self):
        self.browser.find_element_by_css_selector('input[type=submit][name=_save]').click()
        self._wait_for_excluded_course_runs_page_to_load()

    def assert_form_fields_present(self):
        """ Asserts the correct fields are rendered on the form. """
        # Check the model fields
        actual = []
        for element in self.browser.find_elements_by_class_name('form-row'):
            actual += [_class for _class in element.get_attribute('class').split(' ') if _class.startswith('field-')]

        expected = [
            'field-uuid', 'field-title', 'field-subtitle', 'field-marketing_hook',
            'field-status', 'field-type', 'field-partner', 'field-banner_image',
            'field-banner_image_url', 'field-card_image', 'field-marketing_slug', 'field-overview',
            'field-credit_redemption_overview', 'field-video', 'field-total_hours_of_effort', 'field-weeks_to_complete',
            'field-min_hours_effort_per_week', 'field-max_hours_effort_per_week', 'field-courses',
            'field-order_courses_by_start_date', 'field-custom_course_runs_display', 'field-excluded_course_runs',
            'field-authoring_organizations', 'field-credit_backing_organizations', 'field-one_click_purchase_enabled',
            'field-hidden', 'field-corporate_endorsements', 'field-faq', 'field-individual_endorsements',
            'field-job_outlook_items', 'field-expected_learning_items', 'field-instructor_ordering',
            'field-enrollment_count', 'field-recent_enrollment_count', 'field-credit_value',
        ]
        self.assertEqual(actual, expected)

    def test_program_creation(self):
        url = self._build_url(reverse(self.create_view_name))
        self.browser.get(url)
        self._wait_for_add_edit_page_to_load()
        self.assert_form_fields_present()

        program = factories.ProgramFactory.build(
            partner=Partner.objects.first(),
            status=ProgramStatus.Unpublished,
            type=ProgramType.objects.first(),
            marketing_slug='foo'
        )
        self.browser.find_element_by_id('id_title').send_keys(program.title)
        self.browser.find_element_by_id('id_subtitle').send_keys(program.subtitle)
        self.browser.find_element_by_id('id_marketing_slug').send_keys(program.marketing_slug)
        self._select_option('id_status', program.status)
        self._select_option('id_type', str(program.type.id))
        self._select_option('id_partner', str(program.partner.id))
        self._submit_program_form()

        actual = Program.objects.latest()
        self.assertEqual(actual.title, program.title)
        self.assertEqual(actual.subtitle, program.subtitle)
        self.assertEqual(actual.marketing_slug, program.marketing_slug)
        self.assertEqual(actual.status, program.status)
        self.assertEqual(actual.type, program.type)
        self.assertEqual(actual.partner, program.partner)

    def test_program_update(self):
        self._navigate_to_edit_page()
        self.assert_form_fields_present()

        title = 'Test Program'
        subtitle = 'This is a test.'

        # Update the program
        data = (
            ('title', title),
            ('subtitle', subtitle),
        )

        for field, value in data:
            element = self.browser.find_element_by_id('id_' + field)
            element.clear()
            element.send_keys(value)

        self._submit_program_form()

        # Verify the program was updated
        self.program = Program.objects.get(pk=self.program.pk)
        self.assertEqual(self.program.title, title)
        self.assertEqual(self.program.subtitle, subtitle)


class ProgramEligibilityFilterTests(SiteMixin, TestCase):
    """ Tests for Program Eligibility Filter class. """
    parameter_name = 'eligible_for_one_click_purchase'

    def test_queryset_method_returns_all_programs(self):
        """ Verify that all programs pass the filter. """
        verified_seat_type = factories.SeatTypeFactory.verified()
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])
        program_filter = ProgramEligibilityFilter(None, {}, None, None)
        course_run = factories.CourseRunFactory()
        factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
        one_click_purchase_eligible_program = factories.ProgramFactory(
            type=program_type,
            courses=[course_run.course],
            one_click_purchase_enabled=True
        )
        one_click_purchase_ineligible_program = factories.ProgramFactory(courses=[course_run.course])
        with self.assertNumQueries(1):
            self.assertEqual(
                list(program_filter.queryset({}, Program.objects.all())),
                [one_click_purchase_eligible_program, one_click_purchase_ineligible_program]
            )

    def test_queryset_method_returns_eligible_programs(self):
        """ Verify that one click purchase eligible programs pass the filter. """
        verified_seat_type = factories.SeatTypeFactory.verified()
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])
        program_filter = ProgramEligibilityFilter(None, {self.parameter_name: 1}, None, None)
        course_run = factories.CourseRunFactory(end=None, enrollment_end=None,)
        factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
        one_click_purchase_eligible_program = factories.ProgramFactory(
            type=program_type,
            courses=[course_run.course],
            one_click_purchase_enabled=True,
        )
        with self.assertNumQueries(FuzzyInt(11, 2)):
            self.assertEqual(
                list(program_filter.queryset({}, Program.objects.all())),
                [one_click_purchase_eligible_program]
            )

    def test_queryset_method_returns_ineligible_programs(self):
        """ Verify programs ineligible for one-click purchase do not pass the filter. """
        program_filter = ProgramEligibilityFilter(None, {self.parameter_name: 0}, None, None)
        one_click_purchase_ineligible_program = factories.ProgramFactory(one_click_purchase_enabled=False)
        with self.assertNumQueries(4):
            self.assertEqual(
                list(program_filter.queryset({}, Program.objects.all())),
                [one_click_purchase_ineligible_program]
            )


class PersonPositionAdminTest(TestCase):
    """Tests for person position admin."""

    def setUp(self):
        super(PersonPositionAdminTest, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.person = Person.objects.create()
        self.person_position = Position.objects.create(person=self.person, title='foo')
        self.person_position_admin = PositionAdmin(self.person_position, AdminSite())
        self.request = HttpRequest()
        self.request.user = self.user

    def test_delete_permission(self):
        """
        Tests that users cannot delete entries
        """
        self.assertFalse(self.person_position_admin.has_delete_permission(self.request))

    def test_delete_action(self):
        """Tests that user can not have delete action"""
        self.assertNotIn('delete_selected', self.person_position_admin.get_actions(self.request))


class PathwayAdminTest(TestCase):
    """Tests for credit pathway admin."""

    def test_program_with_same_partner(self):
        """
        Test happy path with same program partner as parent pathway
        """
        partner1 = PartnerFactory()
        program1 = factories.ProgramFactory(partner=partner1)
        data = {
            'partner': partner1.id,
            'name': 'Name',
            'org_name': 'Org',
            'email': 'email@example.com',
            'programs': [program1.id],
            'pathway_type': PathwayType.CREDIT.value,
        }
        form = PathwayAdminForm(data=data)

        self.assertDictEqual(form.errors, {})

    def test_program_with_different_partner(self):
        """
        Tests that contained programs can't be for the wrong partner
        """
        partner1 = PartnerFactory()
        partner2 = PartnerFactory()
        program1 = factories.ProgramFactory(partner=partner1)
        program2 = factories.ProgramFactory(partner=partner2, title='partner2 program')
        data = {
            'partner': partner1.id,
            'name': 'Name',
            'org_name': 'Org',
            'email': 'email@example.com',
            'programs': [program1.id, program2.id],
            'pathway_type': PathwayType.INDUSTRY.value,
        }
        form = PathwayAdminForm(data=data)

        self.assertDictEqual(form.errors, {
            '__all__': ['These programs are for a different partner than the pathway itself: partner2 program']
        })
