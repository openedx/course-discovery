# pylint: disable=no-member
import json

import ddt
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm

from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.constants import INTERNAL_USER_GROUP_NAME
from course_discovery.apps.publisher.models import Course
from course_discovery.apps.publisher.tests import factories, JSON_CONTENT_TYPE


@ddt.ddt
class CourseRoleAssignmentViewTests(TestCase):

    def setUp(self):
        super(CourseRoleAssignmentViewTests, self).setUp()
        self.course = factories.CourseFactory()

        # Create an internal user group and assign four users.
        self.internal_user = UserFactory()
        internal_user_group = Group.objects.get(name=INTERNAL_USER_GROUP_NAME)

        internal_user_group.user_set.add(self.internal_user)
        self.other_internal_users = []
        for __ in range(3):
            user = UserFactory()
            self.other_internal_users.append(user)
            internal_user_group.user_set.add(user)

        assign_perm(Course.VIEW_PERMISSION, internal_user_group, self.course)

        organization = OrganizationFactory()
        self.course.organizations.add(organization)

        # Create three internal user course roles for internal users against a course
        # so we can test change role assignment on these roles.
        for user, role in zip(self.other_internal_users, PublisherUserRole.choices):
            factories.CourseUserRoleFactory(course=self.course, user=user, role=role)

        self.client.login(username=self.internal_user.username, password=USER_PASSWORD)

    def get_role_assignment_url(self, user_course_role):
        return reverse(
            'publisher:api:course_role_assignments', kwargs={'pk': user_course_role.id}
        )

    def test_role_assignment_with_non_internal_user(self):
        """ Verify non-internal users cannot change role assignments. """

        non_internal_user = UserFactory()
        assign_perm(Course.VIEW_PERMISSION, non_internal_user, self.course)

        self.client.logout()
        self.client.login(username=non_internal_user.username, password=USER_PASSWORD)

        response = self.client.patch(
            self.get_role_assignment_url(self.course.course_user_roles.first()),
            data=json.dumps({'user': non_internal_user.id}),
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

        # create group and add test users in the group
        group = factories.GroupFactory()
        self.org_user1 = UserFactory.create(full_name="org user1")
        self.org_user2 = UserFactory.create(full_name="org user2")
        group.user_set.add(self.org_user1)
        group.user_set.add(self.org_user2)

        self.organization = OrganizationFactory()
        factories.OrganizationExtensionFactory.create(organization=self.organization, group=group)

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
