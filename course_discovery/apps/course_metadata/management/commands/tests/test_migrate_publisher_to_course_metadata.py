import ddt
import mock
from django.core.management import CommandError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.course_metadata.management.commands.migrate_publisher_to_course_metadata import Command
from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseRun, MigratePublisherToCourseMetadataConfig
)
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.tests import factories as publisher_factories


@ddt.ddt
class TestMigratePublisherToCourseMetadata(TestCase):
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.migrate_publisher_to_course_metadata.logger'  # pylint: disable=line-too-long

    def setUp(self):
        super(TestMigratePublisherToCourseMetadata, self).setUp()
        self.partner = PartnerFactory()
        self.user_1 = UserFactory()
        self.org_1 = factories.OrganizationFactory(partner=self.partner)
        self.course_1 = factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+101x',
            title='Old Title',
        )

        self.publisher_course_1 = publisher_factories.CourseFactory(number='101x', title='New Title')
        self.publisher_course_1.organizations.add(self.org_1)  # pylint: disable=no-member
        publisher_factories.CourseRunFactory(
            course=self.publisher_course_1,
            lms_course_id='course-v1:{org}+{number}+1T2019'.format(
                org=self.org_1.key, number=self.publisher_course_1.number
            ),
        )
        self.course_team_user_role_1 = publisher_factories.CourseUserRoleFactory(
            course=self.publisher_course_1,
            user=self.user_1,
            role=PublisherUserRole.CourseTeam
        )
        # Creating so we can ensure these user roles are not turned into CourseEditors
        publisher_factories.CourseUserRoleFactory(
            course=self.publisher_course_1,
            role=PublisherUserRole.ProjectCoordinator
        )

    def test_handle_with_one_org(self):
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=self.org_1.key)
        self.assertEqual(CourseEditor.objects.count(), 0)

        Command().handle()

        self.assertEqual(CourseEditor.objects.count(), 1)
        draft_course = Course.everything.get(key=self.course_1.key, draft=True)

        editor = CourseEditor.objects.first()
        self.assertEqual(editor.user, self.user_1)
        self.assertEqual(editor.user, self.course_team_user_role_1.user)
        self.assertEqual(editor.course, draft_course)

        # When we publish to course_metadata from publisher, we should update all the fields.
        self.assertEqual(draft_course.title, self.publisher_course_1.title)

    def test_handle_with_multiple_orgs(self):
        user_2 = UserFactory()
        org_2 = factories.OrganizationFactory(partner=self.partner)
        course_2 = factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[org_2],
            key=org_2.key + '+102x',
            title='Old Title 2'
        )
        publisher_course_2 = publisher_factories.CourseFactory(number='102x', title='New Title 2')
        publisher_course_2.organizations.add(org_2)  # pylint: disable=no-member
        publisher_factories.CourseRunFactory(
            course=publisher_course_2,
            lms_course_id='course-v1:{org}+{number}+1T2019'.format(
                org=org_2.key, number=publisher_course_2.number
            ),
        )
        course_team_user_role_2 = publisher_factories.CourseUserRoleFactory(
            course=publisher_course_2,
            user=user_2,
            role=PublisherUserRole.CourseTeam
        )
        publisher_factories.CourseUserRoleFactory(
            course=publisher_course_2,
            role=PublisherUserRole.ProjectCoordinator
        )
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=','.join([self.org_1.key, org_2.key]))
        self.assertEqual(CourseEditor.objects.count(), 0)

        Command().handle()

        self.assertEqual(CourseEditor.objects.count(), 2)

        draft_course_1 = Course.everything.get(key=self.course_1.key, draft=True)
        editor_1 = CourseEditor.objects.get(user=self.user_1)
        self.assertEqual(editor_1.user, self.course_team_user_role_1.user)
        self.assertEqual(editor_1.course, draft_course_1)

        draft_course_2 = Course.everything.get(key=course_2.key, draft=True)
        editor_2 = CourseEditor.objects.get(user=user_2)
        self.assertEqual(editor_2.user, course_team_user_role_2.user)
        self.assertEqual(editor_2.course, draft_course_2)

        self.assertEqual(draft_course_1.title, self.publisher_course_1.title)
        self.assertEqual(draft_course_2.title, publisher_course_2.title)

    def test_handle_with_multiple_course_team_members(self):
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=self.org_1.key)
        extra_user_1 = UserFactory()
        extra_user_1_course_team_user_role = publisher_factories.CourseUserRoleFactory(
            course=self.publisher_course_1,
            user=extra_user_1,
            role=PublisherUserRole.CourseTeam
        )
        extra_user_2 = UserFactory()
        extra_user_2_course_team_user_role = publisher_factories.CourseUserRoleFactory(
            course=self.publisher_course_1,
            user=extra_user_2,
            role=PublisherUserRole.CourseTeam
        )
        self.assertEqual(CourseEditor.objects.count(), 0)

        Command().handle()

        self.assertEqual(CourseEditor.objects.count(), 3)

        draft_course = Course.everything.get(key=self.course_1.key, draft=True)
        editor_1 = CourseEditor.objects.get(user=self.user_1)
        self.assertEqual(editor_1.user, self.course_team_user_role_1.user)
        self.assertEqual(editor_1.course, draft_course)

        editor_2 = CourseEditor.objects.get(user=extra_user_1)
        self.assertEqual(editor_2.user, extra_user_1_course_team_user_role.user)
        self.assertEqual(editor_2.course, draft_course)

        editor_3 = CourseEditor.objects.get(user=extra_user_2)
        self.assertEqual(editor_3.user, extra_user_2_course_team_user_role.user)
        self.assertEqual(editor_3.course, draft_course)

    def test_handle_with_no_course_metadata_course(self):
        """
        If the course_metadata version of the Publisher Course and Course run doesn't exist, this
        command should create them.
        """
        self.course_1.delete()
        user = UserFactory()
        org = factories.OrganizationFactory(partner=self.partner)
        publisher_course = publisher_factories.CourseFactory(number='102x', title='New Title 2')
        publisher_course.organizations.add(org)  # pylint: disable=no-member
        lms_course_id = 'course-v1:{org}+{number}+1T2019'.format(org=org.key, number=publisher_course.number)
        publisher_course_run = publisher_factories.CourseRunFactory(
            course=publisher_course,
            lms_course_id=lms_course_id,
        )
        course_team_user_role = publisher_factories.CourseUserRoleFactory(
            course=publisher_course,
            user=user,
            role=PublisherUserRole.CourseTeam
        )
        # Shouldn't show up as a CourseEditor
        publisher_factories.CourseUserRoleFactory(
            course=publisher_course,
            role=PublisherUserRole.ProjectCoordinator
        )
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=','.join([org.key]))

        self.assertEqual(CourseEditor.objects.count(), 0)
        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        Command().handle()

        self.assertEqual(CourseEditor.objects.count(), 1)

        editor = CourseEditor.objects.first()
        self.assertEqual(editor.user, user)
        self.assertEqual(editor.user, course_team_user_role.user)

        course_key = '{org}+{number}'.format(org=org.key, number=publisher_course.number)
        draft_course = Course.everything.get(key=course_key, draft=True)
        self.assertEqual(editor.course, draft_course)

        self.assertEqual(Course.everything.count(), 1)
        self.assertEqual(CourseRun.everything.count(), 1)

        self.assertEqual(draft_course.title, publisher_course.title)
        self.assertEqual(draft_course.short_description, publisher_course.short_description)
        self.assertEqual(draft_course.full_description, publisher_course.full_description)

        draft_course_run = CourseRun.everything.get(key=lms_course_id, draft=True)
        self.assertEqual(draft_course_run.start, publisher_course_run.start)
        self.assertEqual(draft_course_run.end, publisher_course_run.end)
        self.assertEqual(draft_course_run.weeks_to_complete, publisher_course_run.length)

    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_config(self, mock_logger):
        configs = MigratePublisherToCourseMetadataConfig.objects.all()
        self.assertEqual(configs.count(), 0)

        try:
            Command().handle()
        except CommandError as e:
            self.assertEqual(str(e), 'No organization keys were defined.')
        mock_logger.error.assert_called_with(
            'No organization keys were defined. Please add organization keys to the '
            'MigratePublisherToCourseMetadataConfig model.'
        )

    @ddt.data('NotARealOrgKey', 'FakeOrg1,FakeOrg2,FakeOrg3')
    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_matched_org_keys(self, org_keys, mock_logger):
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=org_keys)

        try:
            Command().handle()
        except CommandError as e:
            self.assertEqual(
                str(e), 'The following organization keys were not valid for any exisiting organizations: '
                        '{org_keys}.'.format(org_keys=org_keys.split(','))
            )
        for key in org_keys.split(','):
            mock_logger.exception.assert_any_call(
                'Organization key [{key}] is not a valid key for any existing organization.'.format(key=key)
            )

    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_matched_publisher_course(self, mock_logger):
        factories.MigratePublisherToCourseMetadataConfigFactory(org_keys=self.org_1.key)
        course_number = '777x'
        factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+' + course_number,
            draft=True,
        )
        self.assertEqual(CourseEditor.objects.count(), 0)

        Command().handle()

        mock_logger.exception.assert_any_call(
            'Course with course number [{course_number}] is not a valid course number for any '
            'existing course in the Publisher tables. As such, there can be no Course User Roles to '
            'move to Course Editors.'.format(course_number=course_number)
        )

        # We still expect CourseEditors to be created for all courses that had a match in Publisher
        # and course team members defined.
        self.assertEqual(CourseEditor.objects.count(), 1)
        editor = CourseEditor.objects.first()
        self.assertEqual(editor.user, self.user_1)
        self.assertEqual(editor.user, self.course_team_user_role_1.user)
        draft_course = Course.everything.get(key=self.course_1.key, draft=True)
        self.assertEqual(editor.course, draft_course)
