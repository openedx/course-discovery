import itertools

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.forms import ProgramAdminForm
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.tests.helpers import make_image_file


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
        self.assertEqual(3, len(self.program.course_runs.all()))

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
        self.assertEqual(2, len(self.program.course_runs.all()))

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
        self.assertEqual(4, len(self.program.course_runs.all()))
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
