import ddt
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import get_group_perms

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.constants import PROJECT_COORDINATOR_GROUP_NAME, REVIEWER_GROUP_NAME
from course_discovery.apps.publisher.forms import CourseRunAdminForm
from course_discovery.apps.publisher.models import CourseRun, OrganizationExtension
from course_discovery.apps.publisher.tests import factories

USER_PASSWORD = 'password'


# pylint: disable=no-member
@ddt.ddt
class AdminTests(TestCase):
    """ Tests Admin page."""

    def setUp(self):
        super(AdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course_run = factories.CourseRunFactory(changed_by=self.user, lms_course_id='')
        self.run_state = factories.CourseRunStateFactory(
            course_run=self.course_run
        )
        self.change_url = reverse('admin:publisher_courserun_add')
        self.form = self.client.get(self.change_url)

        self.assertFalse(CourseRun.objects.filter(lms_course_id__isnull=True).exists())

    def test_update_course_form(self):
        """ Verify that admin save the none in case of empty lms-course-id."""

        # in case of empty string no data appears.
        data = self._post_data(self.course_run)
        self.client.post(self.change_url, data=data)
        self.assertTrue(CourseRun.objects.filter(lms_course_id__isnull=True).exists())

    def test_update_course_with_valid_key(self):
        """ Verify that admin save the none in case of empty lms-course-id."""

        key = 'test/course/key'
        data = self._post_data(self.course_run)
        data['lms_course_id'] = key
        self.client.post(self.change_url, data=data)
        self.assertTrue(CourseRun.objects.filter(lms_course_id=key).exists())

    def test_error_with_invalid_key(self):
        """ Verify that admin forms return error in case of invalid course-id."""
        key = 'test'
        data = self._post_data(self.course_run)
        data['lms_course_id'] = key
        form = CourseRunAdminForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {'lms_course_id': ['Invalid course key.']})

    def _post_data(self, course_run):
        return {
            'lms_course_id': '',
            'pacing_type': course_run.pacing_type,
            'course': course_run.course.id,
            'start_0': course_run.start.date(),
            'start_1': course_run.start.time(),
            'end_0': course_run.end.date(),
            'end_1': course_run.end.time(),
            'state': self.run_state.id,
            'contacted_partner_manager': course_run.contacted_partner_manager,
            'changed_by': self.user.id,

        }

    def _assert_response(self, url):
        """ Verify page loads successfully."""
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class OrganizationExtensionAdminTests(TestCase):
    """ Tests for OrganizationExtensionAdmin."""

    def setUp(self):
        super(OrganizationExtensionAdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.run_state = factories.CourseRunStateFactory()
        self.admin_page_url = reverse('admin:publisher_organizationextension_add')

    def test_organization_extension_permission(self):
        """
        Verify that required permissions assigned to OrganizationExtension object.
        """
        test_organization = OrganizationFactory()
        test_group = factories.GroupFactory()
        post_data = {'organization': test_organization.id, 'group': test_group.id}
        self.client.post(self.admin_page_url, data=post_data)

        organization_extension = OrganizationExtension.objects.get(organization=test_organization, group=test_group)

        expected_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN,
            OrganizationExtension.EDIT_COURSE_RUN
        ]

        course_team_permissions = get_group_perms(test_group, organization_extension)
        self.assertEqual(sorted(course_team_permissions), sorted(expected_permissions))

        marketing_permissions = get_group_perms(Group.objects.get(name=REVIEWER_GROUP_NAME), organization_extension)
        self.assertEqual(list(marketing_permissions), [OrganizationExtension.EDIT_COURSE])

        pc_permissions = get_group_perms(Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME), organization_extension)
        self.assertEqual(list(pc_permissions), [OrganizationExtension.EDIT_COURSE_RUN])
