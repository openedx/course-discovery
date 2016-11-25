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
