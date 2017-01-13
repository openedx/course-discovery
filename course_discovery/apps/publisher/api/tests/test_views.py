# pylint: disable=no-member
import json

import ddt
from mock import patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import INTERNAL_USER_GROUP_NAME
from course_discovery.apps.publisher.models import CourseRun, OrganizationExtension
from course_discovery.apps.publisher.tests import factories, JSON_CONTENT_TYPE


@ddt.ddt
class CourseRoleAssignmentViewTests(TestCase):

    def setUp(self):
        super(CourseRoleAssignmentViewTests, self).setUp()
        self.course = factories.CourseFactory()

        # Create an internal user group and assign four users.
        self.internal_user = UserFactory()
        self.internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)

        self.internal_user_group.user_set.add(self.internal_user)
        self.other_internal_users = []
        for __ in range(3):
            user = UserFactory()
            self.other_internal_users.append(user)
            self.internal_user_group.user_set.add(user)

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)

        # Create three internal user course roles for internal users against a course
        # so we can test change role assignment on these roles.
        roles = [role for role, __ in PublisherUserRole.choices]
        for user, role in zip(self.other_internal_users, roles):
            factories.CourseUserRoleFactory(course=self.course, user=user, role=role)

        self.client.login(username=self.internal_user.username, password=USER_PASSWORD)

    def get_role_assignment_url(self, user_course_role):
        return reverse(
            'publisher:api:course_role_assignments', kwargs={'pk': user_course_role.id}
        )

    def test_role_assignment_with_non_internal_user(self):
        """ Verify non-internal users cannot change role assignments. """

        non_internal_user = UserFactory()

        self.client.logout()
        self.client.login(username=non_internal_user.username, password=USER_PASSWORD)

        response = self.client.patch(
            self.get_role_assignment_url(self.course.course_user_roles.first()),
            data=json.dumps({'user': non_internal_user.id}),
            content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 403)

    def test_role_assignment_with_view_permissions(self):
        """ Verify user having permissions can change role assignments. """

        # mocked the check_roles_access because it checks whether user is part of internal group
        # or has org permissions. So if this method returns True then permission check by passes.

        user = UserFactory()
        user.groups.add(self.internal_user_group)

        # assigning permission to the organization group
        user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

        with patch('course_discovery.apps.publisher.api.permissions.check_roles_access') as mock_method:
            mock_method.return_value = False

            response = self.client.patch(
                self.get_role_assignment_url(self.course.course_user_roles.first()),
                data=json.dumps({'user': user.id}),
                content_type=JSON_CONTENT_TYPE
            )
            self.assertEqual(response.status_code, 200)

    def test_role_assignment_without_view_permissions(self):
        """ Verify user having wrong permissions cannot change role assignments. """

        # mocked the check_roles_access because it checks whether user is part of internal group
        # or has org permissions. So if this method returns True then permission check by passes.

        user = UserFactory()
        user.groups.add(self.internal_user_group)

        # assigning permission to the organization group
        user.groups.add(self.organization_extension.group)

        assign_perm(
            OrganizationExtension.EDIT_COURSE_RUN, self.organization_extension.group, self.organization_extension
        )

        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

        with patch('course_discovery.apps.publisher.api.permissions.check_roles_access') as mock_method:
            mock_method.return_value = False
            response = self.client.patch(
                self.get_role_assignment_url(self.course.course_user_roles.first()),
                data=json.dumps({'user': user.id}),
                content_type=JSON_CONTENT_TYPE
            )
            self.assertEqual(response.status_code, 403)

    def get_user_course_roles(self):
        return self.course.course_user_roles.all()

    @ddt.data(
        PublisherUserRole.PartnerCoordinator,
        PublisherUserRole.MarketingReviewer,
        PublisherUserRole.Publisher
    )
    def test_change_role_assignment_with_internal_user(self, role_name):
        """ Verify that internal user can change course role assignment for
        all three internal user course roles to another internal user.
        """
        user_course_role = self.course.course_user_roles.get(role__icontains=role_name)
        response = self.client.patch(
            self.get_role_assignment_url(user_course_role),
            data=json.dumps({'user': self.internal_user.id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)
        expected = {
            'course': self.course.id,
            'user': self.internal_user.id,
            'role': user_course_role.role
        }
        self.assertDictEqual(response.data, expected)
        self.assertEqual(self.internal_user, self.course.course_user_roles.get(role=user_course_role.role).user)


class OrganizationGroupUserViewTests(TestCase):

    def setUp(self):
        super(OrganizationGroupUserViewTests, self).setUp()

        user = UserFactory.create(username="test_user", password=USER_PASSWORD)
        self.client.login(username=user.username, password=USER_PASSWORD)

        organization_extension = factories.OrganizationExtensionFactory()
        self.org_user1 = UserFactory.create(full_name="org user1")
        self.org_user2 = UserFactory.create(full_name="org user2")
        organization_extension.group.user_set.add(self.org_user1)
        organization_extension.group.user_set.add(self.org_user2)
        self.organization = organization_extension.organization

    def test_get_organization_user_group(self):
        """ Verify that view returns list of users associated with the group
        related to given organization id.
        """
        response = self.client.get(path=self._get_organization_group_user_url(self.organization.id),
                                   content_type=JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 200)

        expected_results = [
            {
                "id": self.org_user1.id,
                "full_name": self.org_user1.full_name
            },
            {
                "id": self.org_user2.id,
                "full_name": self.org_user2.full_name
            }
        ]

        self.assertEqual(json.loads(response.content.decode("utf-8"))["results"], expected_results)

    def test_get_organization_not_found(self):
        """ Verify that view returns status=404 if organization is not found
        in OrganizationExtension.
        """
        response = self.client.get(path=self._get_organization_group_user_url(org_id=0000),
                                   content_type=JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 404)

    def _get_organization_group_user_url(self, org_id):
        return reverse(
            'publisher:api:organization_group_users', kwargs={'pk': org_id}
        )


class UpdateCourseKeyViewTests(TestCase):

    def setUp(self):
        super(UpdateCourseKeyViewTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course_run.course.organizations.add(self.organization_extension.organization)

        self.update_course_key_url = reverse(
            'publisher:api:update_course_key', kwargs={'pk': self.course_run.id}
        )

        factories.CourseUserRoleFactory(
            role=PublisherUserRole.PartnerCoordinator,
            course=self.course_run.course,
            user=self.user
        )

        factories.UserAttributeFactory(user=self.user, enable_email_notification=True)
        toggle_switch('enable_publisher_email_notifications', True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_update_course_key_with_errors(self):
        """
        Test that api returns error with invalid course key.
        """
        invalid_course_id = 'invalid-course-key'
        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': invalid_course_id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('non_field_errors'), ['Invalid course key [{}]'.format(invalid_course_id)]
        )

    def test_update_course_key(self):
        """
        Test that internal user can update `lms_course_id` for a course run.
        """
        # Verify that `lms_course_id` and `changed_by` are None
        self.assert_course_key_and_changed_by()

        lms_course_id = 'course-v1:edxTest+TC12+2050Q1'
        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': lms_course_id}),
            content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 200)

        # Verify that `lms_course_id` and `changed_by` are not None
        self.assert_course_key_and_changed_by(lms_course_id=lms_course_id, changed_by=self.user)

        # Assert email sent
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio instance created',
            'EdX has created a Studio instance for '
        )

    def assert_course_key_and_changed_by(self, lms_course_id=None, changed_by=None):
        self.course_run = CourseRun.objects.get(id=self.course_run.id)

        self.assertEqual(self.course_run.lms_course_id, lms_course_id)
        self.assertEqual(self.course_run.changed_by, changed_by)

    def assert_email_sent(self, object_path, subject, expected_body):
        """
        DRY method to assert sent email data.
        """
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([settings.PUBLISHER_FROM_EMAIL], mail.outbox[0].to)
        self.assertEqual([self.user.email], mail.outbox[0].bcc)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)
