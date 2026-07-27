from django.test import TestCase

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.forms import ProgramAdminForm
from course_discovery.apps.course_metadata.tests import factories


class ProgramAdminFormTests(SiteMixin, TestCase):
    """ Tests ProgramAdminForm. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = UserFactory(is_staff=True, is_superuser=True)
        cls.course_runs = factories.CourseRunFactory.create_batch(3)
        cls.courses = [course_run.course for course_run in cls.course_runs]
        cls.product_source = factories.SourceFactory()

        cls.excluded_course_run = factories.CourseRunFactory(course=cls.courses[0])
        cls.program = factories.ProgramFactory(
            courses=cls.courses,
            excluded_course_runs=[cls.excluded_course_run],
            partner=cls.partner,
        )
        cls.org_1 = factories.OrganizationFactory(certificate_logo_image=None)
        cls.org_2 = factories.OrganizationFactory(certificate_logo_image=None)
        cls.org_3 = factories.OrganizationFactory()

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
            'partner': self.program.partner.id,
            'product_source': self.product_source.id,
            'authoring_organizations': [self.org_1.id, self.org_2.id, self.org_3.id],
        }

    def test_clean_authoring_organizations_with_empty_certificate_logo_image(self):
        """
        Test verifies that the form is invalid if certificate_logo_image
        is empty for any of the authoring_organizations.
        """
        data = self._post_data()
        form = ProgramAdminForm(data=data)
        self.assertFalse(form.is_valid())
        expected_error_message = f'Certificate logo image cannot be empty for organizations: ' \
                                 f'{self.org_1.name}, {self.org_2.name}.'

        self.assertEqual(form.errors['authoring_organizations'][0], expected_error_message)

    def test_clean_authoring_organizations_with_non_empty_certificate_logo_image(self):
        """
        Test verifies that the form is valid only if certificate_logo_image
        is not empty for all authoring_organizations.
        """
        self.org_1.certificate_logo_image = 'logo1.jpg'
        self.org_1.save()
        self.org_2.certificate_logo_image = 'logo2.jpg'
        self.org_2.save()
        data = self._post_data()
        form = ProgramAdminForm(data=data)

        self.assertTrue(form.is_valid())

    def test_b2c_program_with_only_b2c_courses_can_be_saved(self):
        enabled_course_1 = factories.CourseFactory(
            title='B2C-enabled course 1',
            b2c_subscription_inclusion=True,
        )
        enabled_course_2 = factories.CourseFactory(
            title='B2C-enabled course 2',
            b2c_subscription_inclusion=True,
        )

        data = self._post_data(status=ProgramStatus.Unpublished)
        data['authoring_organizations'] = []
        data['courses'] = [enabled_course_1.id, enabled_course_2.id]
        data['b2c_subscription_inclusion'] = 'on'

        form = ProgramAdminForm(data=data)
        self.assertTrue(form.is_valid())

        program = form.save()
        self.assertTrue(program.b2c_subscription_inclusion)
        self.assertEqual(list(program.courses.order_by('id')), [enabled_course_1, enabled_course_2])

    def test_b2c_program_with_non_b2c_course_cannot_be_saved(self):
        enabled_course = factories.CourseFactory(
            title='B2C-enabled course',
            b2c_subscription_inclusion=True,
        )
        disabled_course = factories.CourseFactory(
            title='Non-B2C course',
            b2c_subscription_inclusion=False,
        )
        disabled_course_2 = factories.CourseFactory(
            title='Non-B2C course 2',
            b2c_subscription_inclusion=False,
        )

        data = self._post_data(status=ProgramStatus.Unpublished)
        data['authoring_organizations'] = []
        data['courses'] = [enabled_course.id, disabled_course.id, disabled_course_2.id]
        data['b2c_subscription_inclusion'] = 'on'

        form = ProgramAdminForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['__all__'],
            [
                'All courses in a B2C subscription program must support B2C subscription inclusion. '
                'Remove or update the following courses before saving: Non-B2C course, Non-B2C course 2.'
            ]
        )

    def test_non_b2c_program_can_be_saved_with_mixed_courses(self):
        enabled_course = factories.CourseFactory(
            title='B2C-enabled course',
            b2c_subscription_inclusion=True,
        )
        disabled_course = factories.CourseFactory(
            title='Non-B2C course',
            b2c_subscription_inclusion=False,
        )

        data = self._post_data(status=ProgramStatus.Unpublished)
        data['authoring_organizations'] = []
        data['courses'] = [enabled_course.id, disabled_course.id]

        form = ProgramAdminForm(data=data)
        self.assertTrue(form.is_valid())

        program = form.save()
        self.assertFalse(program.b2c_subscription_inclusion)
        self.assertEqual(list(program.courses.order_by('id')), [enabled_course, disabled_course])
