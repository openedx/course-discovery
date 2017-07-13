# pylint: disable=no-member
import json
from urllib.parse import quote

import ddt
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core import mail
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from mock import mock, patch
from opaque_keys.edx.keys import CourseKey
from testfixtures import LogCapture

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PersonFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.api import views
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState,
                                                    OrganizationExtension, Seat)
from course_discovery.apps.publisher.tests import JSON_CONTENT_TYPE, factories


@ddt.ddt
class CourseRoleAssignmentViewTests(TestCase):

    def setUp(self):
        super(CourseRoleAssignmentViewTests, self).setUp()
        self.course = factories.CourseFactory()

        # Create an internal user group and assign four users because we have
        # four different roles for every course.
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
        """ Verify that only authorized users can change role assignments. """
        user = UserFactory()
        user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )
        course_team_role = factories.CourseUserRoleFactory(
            course=self.course, user=user, role=PublisherUserRole.CourseTeam
        )

        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

        response = self.client.patch(
            self.get_role_assignment_url(course_team_role),
            data=json.dumps({'user': user.id}),
            content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 200)

    def test_role_assignment_without_view_permissions(self):
        """ Verify cannot change role assignments without permission. """
        user = UserFactory()
        self.client.logout()
        self.client.login(username=user.username, password=USER_PASSWORD)

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
        PublisherUserRole.ProjectCoordinator,
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
        self.assertEqual(len(mail.outbox), 1)


class OrganizationGroupUserViewTests(TestCase):

    def setUp(self):
        super(OrganizationGroupUserViewTests, self).setUp()

        user = UserFactory.create(username="test_user", password=USER_PASSWORD)
        self.client.login(username=user.username, password=USER_PASSWORD)

        organization_extension = factories.OrganizationExtensionFactory()
        self.org_user1 = UserFactory.create(full_name="org user1")
        self.org_user2 = UserFactory.create(first_name='', last_name='', full_name='')
        organization_extension.group.user_set.add(*[self.org_user1, self.org_user2])
        self.organization = organization_extension.organization

    def test_get_organization_user_group(self):
        """
        Verify that view returns list of users associated with the group related to given organization id.
        """
        response = self.client.get(
            path=self._get_organization_group_user_url(self.organization.id), content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 200)
        expected_results = [
            {
                "id": self.org_user1.id,
                "full_name": self.org_user1.full_name
            },
            {
                "id": self.org_user2.id,
                "full_name": self.org_user2.username
            }
        ]

        self.assertIn(expected_results[0], json.loads(response.content.decode("utf-8"))["results"])
        self.assertIn(expected_results[1], json.loads(response.content.decode("utf-8"))["results"])

    def test_get_organization_not_found(self):
        """
        Verify that view returns status=404 if organization is not found in OrganizationExtension.
        """
        response = self.client.get(path=self._get_organization_group_user_url(org_id=0000),
                                   content_type=JSON_CONTENT_TYPE)
        self.assertEqual(response.status_code, 404)

    def _get_organization_group_user_url(self, org_id):
        return reverse(
            'publisher:api:organization_group_users', kwargs={'pk': org_id}
        )


class UpdateCourseRunViewTests(TestCase):

    def setUp(self):
        super(UpdateCourseRunViewTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course_run.course.organizations.add(self.organization_extension.organization)

        self.update_course_run_url = reverse(
            'publisher:api:update_course_run', kwargs={'pk': self.course_run.id}
        )

        factories.CourseUserRoleFactory(
            role=PublisherUserRole.ProjectCoordinator,
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
            self.update_course_run_url,
            data=json.dumps({'lms_course_id': invalid_course_id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('lms_course_id'),
            ({'lms_course_id': 'Invalid course key "{lms_course_id}"'.format(lms_course_id=invalid_course_id)})
        )

    def test_update_course_key_without_permission(self):
        """
        Test that api returns status=403 is user dost not have permissions.
        """
        self.user.groups.remove(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        response = self.client.patch(
            self.update_course_run_url,
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
            self.update_course_run_url,
            data=json.dumps({'lms_course_id': lms_course_id}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('lms_course_id'), ['course run with this lms course id already exists.']
        )

    def test_update_course_key(self):
        """
        Test that internal user can update `lms_course_id` for a course run.
        """
        # By default `lms_course_id` and `changed_by` are None
        self.assert_course_key_and_changed_by()

        # create course team role for email
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam, user=self.user
        )

        lms_course_id = 'course-v1:edxTest+TC12+2050Q1'
        response = self.client.patch(
            self.update_course_run_url,
            data=json.dumps({'lms_course_id': lms_course_id}),
            content_type=JSON_CONTENT_TYPE
        )
        self.assertEqual(response.status_code, 200)

        # Verify that `lms_course_id` and `changed_by` are not None
        self.assert_course_key_and_changed_by(lms_course_id=lms_course_id, changed_by=self.user)

        course_key = CourseKey.from_string(lms_course_id)
        # Assert email sent
        self.assert_email_sent(
            reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.course_run.id}),
            'Studio URL created: {title} {run}'.format(title=self.course_run.course.title, run=course_key.run),
            'has created a Studio URL'
        )

    def assert_course_key_and_changed_by(self, lms_course_id=None, changed_by=None):
        """ Helper method to assert course key and changed_by. """
        self.course_run = CourseRun.objects.get(id=self.course_run.id)

        self.assertEqual(self.course_run.lms_course_id, lms_course_id)
        self.assertEqual(self.course_run.changed_by, changed_by)

    def assert_email_sent(self, object_path, subject, expected_body):
        """
        Helper method to assert sent email data.
        """
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([self.user.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        self.assertIn(expected_body, body)
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)

    def test_update_preview_url(self):
        """Verify the user can update course preview url."""
        self.course_run.lms_course_id = 'course-v1:testX+TC167+2018T1'
        self.course_run.save()
        preview_url = 'https://example.com/abc/course'
        factories.CourseRunStateFactory.create(course_run=self.course_run, owner_role=PublisherUserRole.Publisher)
        factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.Publisher
        )
        course_team_role = factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam
        )
        response = self._make_request(preview_url)

        self.assertEqual(response.status_code, 200)
        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertEqual(course_run.preview_url, preview_url)

        course_key = CourseKey.from_string(course_run.lms_course_id)
        subject = 'Review requested: Preview for {course_name} {run_number}'.format(
            course_name=self.course_run.course.title,
            run_number=course_key.run
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([course_team_role.user.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

    def test_update_with_invalid_preview_url(self):
        """Verify that user can't update course preview url if url has invalid format."""
        preview_url = 'invalid_url_format'
        response = self._make_request(preview_url)
        self.assertEqual(response.status_code, 400)

    def _make_request(self, preview_url):
        """ Helper method to make request. """
        return self.client.patch(
            self.update_course_run_url,
            data=json.dumps({'preview_url': preview_url}),
            content_type=JSON_CONTENT_TYPE
        )

    def test_update_preview_url_with_notification_disabled(self):
        """
        Verify that no email sent on update course preview url if
        notification disabled by user.
        """
        preview_url = 'https://example.com/abc/course'
        factories.CourseRunStateFactory.create(course_run=self.course_run, owner_role=PublisherUserRole.Publisher)
        course_team_role = factories.CourseUserRoleFactory(
            course=self.course_run.course, role=PublisherUserRole.CourseTeam
        )
        factories.UserAttributeFactory(user=course_team_role.user, enable_email_notification=False)

        response = self._make_request(preview_url)

        self.assertEqual(response.status_code, 200)
        course_run = CourseRun.objects.get(id=self.course_run.id)
        self.assertEqual(course_run.preview_url, preview_url)
        self.assertEqual(len(mail.outbox), 0)


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
            'tertiary_subject': revision.tertiary_subject.name,
            'level_type': revision.level_type.name,
            'learner_testimonial': revision.learner_testimonial,
            'faq': revision.faq,
            'video_link': revision.video_link
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

        self.course = self.course_state.course
        self.course.image = make_image_file('test_banner.jpg')
        self.course.save()

        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)
        factories.UserAttributeFactory(user=self.user, enable_email_notification=True)
        toggle_switch('enable_publisher_email_notifications', True)

        self.change_state_url = reverse('publisher:api:change_course_state', kwargs={'pk': self.course_state.id})

        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_change_course_state(self):
        """
        Verify that if marketing user change course state, owner role will be changed to `CourseTeam`.
        """
        self.assertNotEqual(self.course_state.name, CourseStateChoices.Review)
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )

        course_team_user = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=course_team_user
        )

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Review}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.course_state = CourseState.objects.get(course=self.course)

        self.assertEqual(self.course_state.name, CourseStateChoices.Review)
        self.assertEqual(self.course_state.owner_role, PublisherUserRole.CourseTeam)
        # Verify that course is marked as reviewed by marketing.
        self.assertTrue(self.course_state.marketing_reviewed)

        subject = 'Review requested: {title}'.format(title=self.course.title)
        self._assert_email_sent(course_team_user, subject)

    @mock.patch('course_discovery.apps.publisher.emails.send_email_for_seo_review')
    def test_change_course_state_with_course_team(self, mocked_seo_review_email):
        """ Verify that if course team admin can change course workflow state,
        owner role will be changed to `MarketingReviewer`.
        """
        self.user.groups.remove(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        self.user.groups.add(self.organization_extension.group)

        self.assertNotEqual(self.course_state.name, CourseStateChoices.Review)
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )

        marketing_user = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=marketing_user
        )

        old_owner_role_modified = self.course_state.owner_role_modified

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Review}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.course_state = CourseState.objects.get(course=self.course)

        self.assertEqual(self.course_state.name, CourseStateChoices.Review)
        self.assertEqual(self.course_state.owner_role, PublisherUserRole.MarketingReviewer)
        self.assertGreater(self.course_state.owner_role_modified, old_owner_role_modified)

        subject = 'Review requested: {title}'.format(title=self.course.title)
        self._assert_email_sent(marketing_user, subject)
        self.assertTrue(mocked_seo_review_email.called)

    def _assert_email_sent(self, user, subject):
        """Helper method to assert sent email data."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([user.email], mail.outbox[0].to)
        self.assertEqual(str(mail.outbox[0].subject), subject)

        body = mail.outbox[0].body.strip()
        object_path = reverse('publisher:publisher_course_detail', kwargs={'pk': self.course.id})
        page_url = 'https://{host}{path}'.format(host=Site.objects.get_current().domain.strip('/'), path=object_path)
        self.assertIn(page_url, body)

    def test_change_course_state_with_error(self):
        """
        Verify that user cannot change course workflow state directly from `Draft` to `Approved`.
        """
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=self.user
        )
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

    def test_mark_as_reviewed(self):
        """
        Verify that user can mark course as reviewed.
        """
        self.course_state.name = CourseStateChoices.Review
        self.course_state.save()

        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.MarketingReviewer, user=self.user
        )
        course_team_user = UserFactory()
        factories.CourseUserRoleFactory(
            course=self.course, role=PublisherUserRole.CourseTeam, user=course_team_user
        )

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Approved}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.course_state = CourseState.objects.get(course=self.course)

        self.assertEqual(self.course_state.name, CourseStateChoices.Approved)

        subject = 'Review complete: {title}'.format(title=self.course.title)
        self._assert_email_sent(course_team_user, subject)


class ChangeCourseRunStateViewTests(TestCase):

    def setUp(self):
        super(ChangeCourseRunStateViewTests, self).setUp()
        self.seat = factories.SeatFactory(type=Seat.VERIFIED, price=2)
        self.course_run = self.seat.course_run

        self.run_state = factories.CourseRunStateFactory(name=CourseRunStateChoices.Draft, course_run=self.course_run)
        self.course_state = factories.CourseStateFactory(
            name=CourseStateChoices.Approved, course=self.course_run.course
        )
        self.user = UserFactory()
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))

        self.change_state_url = reverse('publisher:api:change_course_run_state', kwargs={'pk': self.run_state.id})

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        language_tag = LanguageTag(code='te-st', name='Test Language')
        language_tag.save()
        self.course_run.transcript_languages.add(language_tag)
        self.course_run.language = language_tag
        self.course_run.lms_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_run.course.organizations.add(OrganizationFactory())
        self.course_run.save()

        self.course_run.staff.add(PersonFactory())

        toggle_switch('enable_publisher_email_notifications', True)

    def test_change_course_run_state_with_error(self):
        """
        Verify that user cannot change course-run workflow state directly from `Draft` to `Published`.
        """
        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseRunStateChoices.Published}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 400)

        expected = {
            'name': 'Cannot switch from state `{state}` to `{target_state}`'.format(
                state=self.run_state.name, target_state=CourseRunStateChoices.Published
            )
        }

        self.assertEqual(response.data, expected)

    def test_send_for_review(self):
        """
        Verify that user can change course-run workflow state and owner role will be changed to `CourseTeam`.
        """
        self.run_state.name = CourseRunStateChoices.Draft
        self.run_state.owner_role = PublisherUserRole.ProjectCoordinator
        self.run_state.save()

        self._assign_role(self.course_run.course, PublisherUserRole.ProjectCoordinator, self.user)

        course_team_user = UserFactory()
        self._assign_role(self.course_run.course, PublisherUserRole.CourseTeam, course_team_user)

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Review}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        course_run_state = CourseRunState.objects.get(course_run=self.course_run)

        self.assertEqual(course_run_state.name, CourseRunStateChoices.Review)
        self.assertEqual(course_run_state.owner_role, PublisherUserRole.CourseTeam)

        self.assertEqual(len(mail.outbox), 1)

    def _assign_role(self, course, role, user):
        """ Method to assign course-user-role."""
        factories.CourseUserRoleFactory(
            course=course, role=role, user=user
        )

    def test_mark_as_reviewed(self):
        """
        Verify that course team can approve the changes and owner role will be changed to `Publisher`.
        """
        self.run_state.name = CourseRunStateChoices.Review
        self.run_state.owner_role = PublisherUserRole.CourseTeam
        self.run_state.save()

        self._assign_role(self.course_run.course, PublisherUserRole.CourseTeam, self.user)
        self._assign_role(self.course_run.course, PublisherUserRole.ProjectCoordinator, UserFactory())

        self._assign_role(self.course_run.course, PublisherUserRole.Publisher, UserFactory())

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Approved}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.run_state = CourseRunState.objects.get(course_run=self.course_run)

        self.assertEqual(self.run_state.name, CourseRunStateChoices.Approved)
        self.assertEqual(self.run_state.owner_role, PublisherUserRole.Publisher)

        self.assertEqual(len(mail.outbox), 2)

    def test_mark_as_reviewed_by_pc(self):
        """
        Verify that project coordinator can approve the changes and email not sent to course team.
        """
        self.run_state.name = CourseRunStateChoices.Review
        self.run_state.owner_role = PublisherUserRole.ProjectCoordinator
        self.run_state.save()

        self._assign_role(self.course_run.course, PublisherUserRole.ProjectCoordinator, self.user)
        self._assign_role(self.course_run.course, PublisherUserRole.CourseTeam, UserFactory())

        self._assign_role(self.course_run.course, PublisherUserRole.Publisher, UserFactory())

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseStateChoices.Approved}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.run_state = CourseRunState.objects.get(course_run=self.course_run)

        self.assertEqual(self.run_state.name, CourseRunStateChoices.Approved)
        self.assertEqual(self.run_state.owner_role, PublisherUserRole.Publisher)

        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(self.course_run.course.course_team_admin.email, mail.outbox[0].to)

    def test_preview_accepted(self):
        """
        Verify that user can accept preview for course run and owner role will be changed to `Publisher`.
        """
        course = self.course_run.course
        self.run_state.name = CourseRunStateChoices.Approved
        self.run_state.owner_role = PublisherUserRole.CourseTeam
        self.run_state.save()

        self._assign_role(course, PublisherUserRole.CourseTeam, self.user)
        self._assign_role(course, PublisherUserRole.ProjectCoordinator, UserFactory())

        self._assign_role(course, PublisherUserRole.Publisher, UserFactory())

        self.assertFalse(self.run_state.preview_accepted)

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'preview_accepted': True}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.run_state = CourseRunState.objects.get(course_run=self.course_run)

        self.assertTrue(self.run_state.preview_accepted)
        self.assertEqual(self.run_state.owner_role, PublisherUserRole.Publisher)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([course.publisher.email, course.project_coordinator.email], mail.outbox[0].bcc)

    def test_course_published(self):
        """
        Verify that publisher user can publish course run.
        """
        course = self.course_run.course
        self.run_state.name = CourseRunStateChoices.Approved
        self.run_state.preview_accepted = True
        self.run_state.save()

        self._assign_role(course, PublisherUserRole.Publisher, self.user)
        self._assign_role(course, PublisherUserRole.CourseTeam, UserFactory())

        response = self.client.patch(
            self.change_state_url,
            data=json.dumps({'name': CourseRunStateChoices.Published}),
            content_type=JSON_CONTENT_TYPE
        )

        self.assertEqual(response.status_code, 200)

        self.run_state = CourseRunState.objects.get(course_run=self.course_run)

        self.assertTrue(self.run_state.is_published)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual([course.course_team_admin.email], mail.outbox[0].to)

        course_key = CourseKey.from_string(self.course_run.lms_course_id)
        expected_subject = 'Publication complete: About page for {course_name} {run_number}'.format(
            course_name=course.title,
            run_number=course_key.run
        )
        self.assertEqual(str(mail.outbox[0].subject), expected_subject)
        self.assertIn('has been published', mail.outbox[0].body.strip())


class RevertCourseByRevisionTests(TestCase):

    def setUp(self):
        super(RevertCourseByRevisionTests, self).setUp()
        self.course = factories.CourseFactory(title='first title')

        # update title so that another revision created
        self.course.title = "updated title"
        self.course.save()

        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_revert_course_revision_with_invalid_id(self):
        """Verify that api return 404 error if revision_id does not exists. """
        response = self._revert_course(0000)
        self.assertEqual(response.status_code, 404)

    def test_revert_course_revision_without_authentication(self):
        """Verify that api return authentication error if user is not logged in. """
        self.client.logout()
        revision = self.course.history.first()
        response = self._revert_course(revision.history_id)
        self.assertEqual(response.status_code, 403)

    def test_revert_course_revision(self):
        """Verify that api update the course with the according to the revision id. """

        revision = self.course.history.last()
        self.assertNotEqual(revision.title, self.course.title)
        response = self._revert_course(revision.history_id)
        self.assertEqual(response.status_code, 204)

        course = Course.objects.get(id=self.course.id)
        self.assertEqual(revision.title, course.title)

    def test_update_with_error(self):
        """ Verify that in case of any error api returns proper error message and code."""
        with LogCapture(views.logger.name) as l:
            with patch.object(Course, "save") as mock_method:
                mock_method.side_effect = IntegrityError
                revision = self.course.history.last()
                response = self._revert_course(revision.history_id)
                l.check(
                    (
                        views.logger.name,
                        'ERROR',
                        'Unable to revert the course [{}] for revision [{}].'.format(
                            self.course.id,
                            revision.history_id
                        )
                    )
                )

        self.assertEqual(response.status_code, 400)

    def _revert_course(self, revision_id):
        """Returns response of api against given revision_id."""
        course_revision_path = reverse(
            'publisher:api:course_revision_revert', kwargs={'history_id': revision_id}
        )
        return self.client.put(path=course_revision_path)


class CoursesAutoCompleteTests(TestCase):
    """ Tests for course autocomplete."""

    def setUp(self):
        super(CoursesAutoCompleteTests, self).setUp()
        self.user = UserFactory()
        self.course = factories.CourseFactory(title='Test course 1')
        self.course2 = factories.CourseFactory(title='Test course 2')
        self.organization_extension = factories.OrganizationExtensionFactory()
        self.course.organizations.add(self.organization_extension.organization)
        self.user.groups.add(self.organization_extension.group)
        assign_perm(
            OrganizationExtension.VIEW_COURSE, self.organization_extension.group, self.organization_extension
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.course_autocomplete_url = reverse('publisher:api:course-autocomplete') + '?q={title}'

    def test_course_autocomplete_without_login(self):
        """ Verify course autocomplete without login. """
        self.client.logout()
        self.course_autocomplete_url = self.course_autocomplete_url.format(title='test')
        response = self.client.get(self.course_autocomplete_url)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(
                url=reverse('login'),
                next=quote(self.course_autocomplete_url)
            ),
            status_code=302,
            target_status_code=302
        )

    def test_course_autocomplete_with_course_team(self):
        """ Verify course autocomplete returns data for course team user. """
        response = self.client.get(self.course_autocomplete_url.format(title='test'))
        self._assert_response(response, 1)

        response = self.client.get(
            self.course_autocomplete_url.format(title='dummy')
        )
        self._assert_response(response, 0)

    def test_course_autocomplete_with_admin(self):
        """ Verify course autocomplete returns all courses for publisher admin. """
        self.user.groups.remove(self.organization_extension.group)
        self.user.groups.add(Group.objects.get(name=ADMIN_GROUP_NAME))
        response = self.client.get(self.course_autocomplete_url.format(title='test'))
        self._assert_response(response, 2)

    def test_course_autocomplete_with_internal_user(self):
        """ Verify course autocomplete returns all courses for publisher admin. """
        self.user.groups.remove(self.organization_extension.group)
        self.user.groups.add(Group.objects.get(name=INTERNAL_USER_GROUP_NAME))
        factories.CourseUserRoleFactory(course=self.course2, user=self.user, role=PublisherUserRole.MarketingReviewer)
        response = self.client.get(self.course_autocomplete_url.format(title='test'))
        self._assert_response(response, 1)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(data['results']), expected_length)


class AcceptAllByRevisionTests(TestCase):

    def setUp(self):
        super(AcceptAllByRevisionTests, self).setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.course = factories.CourseFactory(title='first title', changed_by=self.user)

        # update title so that another revision created
        self.course.title = "updated title"
        self.course.changed_by = self.user
        self.course.save()

    def test_update_all_revision_with_invalid_id(self):
        """Verify that api return 404 error if revision_id does not exists. """
        response = self._update_all_by_revision_course(0000)
        self.assertEqual(response.status_code, 404)

    def test_update_all_course_revision_without_authentication(self):
        """Verify that api return authentication error if user is not logged in. """
        self.client.logout()
        revision = self.course.history.first()
        response = self._update_all_by_revision_course(revision.history_id)
        self.assertEqual(response.status_code, 403)

    def test_update_all_course_revision(self):
        """Verify that api update the course with the according to the revision id. """

        # most recent history revision made by user
        revision = self.course.history.latest()
        self.assertEqual(revision.changed_by, self.user)
        self.client.logout()

        # update the course through api and now change-by and history user will the 2nd user.
        user_2 = UserFactory()
        self.client.login(username=user_2.username, password=USER_PASSWORD)
        response = self._update_all_by_revision_course(revision.history_id)
        self.assertEqual(response.status_code, 201)

        revision = self.course.history.latest()
        self.assertEqual(revision.history_user, user_2)
        course = Course.objects.get(id=self.course.id)
        self.assertEqual(course.changed_by, user_2)

    def _update_all_by_revision_course(self, revision_id):
        """Update the course objects by changing just changed-by attr."""
        course_revision_path = reverse(
            'publisher:api:accept_all_revision', kwargs={'history_id': revision_id}
        )
        return self.client.post(path=course_revision_path)
