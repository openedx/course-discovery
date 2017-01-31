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
from course_discovery.apps.publisher.choices import PublisherUserRole, CourseStateChoices
from course_discovery.apps.publisher.constants import INTERNAL_USER_GROUP_NAME
from course_discovery.apps.publisher.models import CourseRun, OrganizationExtension, CourseState
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
        self.other_internal_users = UserFactory.create_batch(4)
        self.internal_user_group.user_set.add(*self.other_internal_users)

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
        PublisherUserRole.PartnerManager,
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
            response.data.get('lms_course_id'),
            ['Invalid course key "{lms_course_id}"'.format(lms_course_id=invalid_course_id)]
        )

    def test_update_course_key_without_permission(self):
        """
        Test that api returns error without permission.
        """
        self.user.groups.remove(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': 'course-v1:edxTest+TC12+2050Q1'}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data.get('detail'), 'You do not have permission to perform this action.'
        )

    def test_update_course_key_with_duplicate(self):
        """
        Test that api returns error if course key already exist.
        """
        lms_course_id = 'course-v1:edxTest+TC12+2050Q1'
        factories.CourseRunFactory(lms_course_id=lms_course_id)

        response = self.client.patch(
            self.update_course_key_url,
            data=json.dumps({'lms_course_id': lms_course_id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('lms_course_id'), ['CourseRun with this lms course id already exists.']
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


class CourseRevisionDetailViewTests(TestCase):

    def setUp(self):
        super(CourseRevisionDetailViewTests, self).setUp()
        self.course = factories.CourseFactory()
        self.course.title = "updated title"
        self.course.save()

        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_get_course_revision(self):
        """Verify that api returns revision object against given revision_id. """
        revision = self.course.history.first()
        expected = {
            'history_id': revision.history_id,
            'title': revision.title,
            'number': revision.number,
            'short_description': revision.short_description,
            'full_description': revision.full_description,
            'expected_learnings': revision.expected_learnings,
            'prerequisites': revision.prerequisites,
            'primary_subject': revision.primary_subject.name,
            'secondary_subject': revision.secondary_subject.name,
            'tertiary_subject': revision.tertiary_subject.name
        }

        response = self._get_response(revision.history_id)
        self.assertEqual(response.data, expected)

    def test_get_course_revision_with_invalid_id(self):
        """Verify that api return 404 error if revision_id does not exists. """
        response = self._get_response(0000)
        self.assertEqual(response.status_code, 404)

    def test_get_course_revision_authentication(self):
        """Verify that api return authentication error if user is not logged in. """
        self.client.logout()
        revision = self.course.history.first()
        response = self._get_response(revision.history_id)
        self.assertEqual(response.status_code, 403)

    def _get_response(self, revision_id):
        """Returns response of api against given revision_id."""
        course_revision_path = reverse(
            'publisher:api:course_revisions', kwargs={'history_id': revision_id}
        )
        return self.client.get(path=course_revision_path)


class ChangeCourseStateViewTests(TestCase):

    def setUp(self):
        super(ChangeCourseStateViewTests, self).setUp()
        self.course_state = factories.CourseStateFactory(name=CourseStateChoices.Draft)
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.change_state_url = reverse('publisher:api:change_course_state', kwargs={'pk': self.course_state.id})

        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_change_course_state(self):
        """
        Verify that publisher user can change course workflow state.
        """
        self.assertNotEqual(self.course_state.name, CourseStateChoices.Review)

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Review}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.course_state = CourseState.objects.get(course=self.course_state.course)

        self.assertEqual(self.course_state.name, CourseStateChoices.Review)

    def test_change_course_state_with_error(self):
        """
        Verify that user cannot change course workflow state directly from `Draft` to `Approved`.
        """
        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Approved}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)

        expected = {
            'name': 'Cannot switch from state `{state}` to `{target_state}`'.format(
                state=self.course_state.name, target_state=CourseStateChoices.Approved
            )
        }

        self.assertEqual(response.data, expected)
