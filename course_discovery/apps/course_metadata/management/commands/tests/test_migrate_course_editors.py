import ddt
import mock
from django.core.management import CommandError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.course_metadata.management.commands.migrate_course_editors import Command
from course_discovery.apps.course_metadata.models import Course, CourseEditor, MigrateCourseEditorsConfig
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.tests import factories as publisher_factories


@ddt.ddt
class TestMigrateCourseEditors(TestCase):
    SAVE_PATH = 'course_discovery.apps.course_metadata.models.CourseEditor.save'
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.migrate_course_editors.logger'

    def setUp(self):
        super(TestMigrateCourseEditors, self).setUp()
        self.partner = PartnerFactory()
        self.user_1 = UserFactory()
        self.org_1 = factories.OrganizationFactory()
        self.course_1 = factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+101x',
        )
        self.publisher_course_1 = publisher_factories.CourseFactory(number='101x')
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

    def handle(self):
        Command().handle()

    def test_handle_with_one_org(self):
        factories.MigrateCourseEditorsConfigFactory(org_keys=self.org_1.key)
        self.assertEqual(CourseEditor.objects.count(), 0)

        self.handle()

        self.assertEqual(CourseEditor.objects.count(), 1)
        editor = CourseEditor.objects.first()
        self.assertEqual(editor.user, self.user_1)
        self.assertEqual(editor.user, self.course_team_user_role_1.user)
        self.assertEqual(editor.course, self.course_1)

    def test_handle_with_multiple_orgs(self):
        user_2 = UserFactory()
        org_2 = factories.OrganizationFactory()
        course_2 = factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[org_2],
            key=org_2.key + '+102x',
        )
        publisher_course_2 = publisher_factories.CourseFactory(number='102x')
        course_team_user_role_2 = publisher_factories.CourseUserRoleFactory(
            course=publisher_course_2,
            user=user_2,
            role=PublisherUserRole.CourseTeam
        )
        publisher_factories.CourseUserRoleFactory(
            course=publisher_course_2,
            role=PublisherUserRole.ProjectCoordinator
        )
        factories.MigrateCourseEditorsConfigFactory(org_keys=','.join([self.org_1.key, org_2.key]))
        self.assertEqual(CourseEditor.objects.count(), 0)

        self.handle()

        self.assertEqual(CourseEditor.objects.count(), 2)

        editor_1 = CourseEditor.objects.get(user=self.user_1)
        self.assertEqual(editor_1.user, self.course_team_user_role_1.user)
        self.assertEqual(editor_1.course, self.course_1)

        editor_2 = CourseEditor.objects.get(user=user_2)
        self.assertEqual(editor_2.user, course_team_user_role_2.user)
        self.assertEqual(editor_2.course, course_2)

    def test_handle_with_multiple_course_team_members(self):
        factories.MigrateCourseEditorsConfigFactory(org_keys=self.org_1.key)
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

        self.handle()

        self.assertEqual(CourseEditor.objects.count(), 3)
        editor_1 = CourseEditor.objects.get(user=self.user_1)
        self.assertEqual(editor_1.user, self.course_team_user_role_1.user)
        self.assertEqual(editor_1.course, self.course_1)

        editor_2 = CourseEditor.objects.get(user=extra_user_1)
        self.assertEqual(editor_2.user, extra_user_1_course_team_user_role.user)
        self.assertEqual(editor_2.course, self.course_1)

        editor_3 = CourseEditor.objects.get(user=extra_user_2)
        self.assertEqual(editor_3.user, extra_user_2_course_team_user_role.user)
        self.assertEqual(editor_3.course, self.course_1)

    def test_handle_with_draft_course(self):
        """
        Draft versions of courses should be preferred over the official version for the course used
        on the CourseEditor
        """
        org = factories.OrganizationFactory()
        factories.MigrateCourseEditorsConfigFactory(org_keys=org.key)
        course_key = org.key + '+blahx'
        draft_course = factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[org],
            key=course_key,
            draft=True,
        )
        # This will create an official version of the draft_course
        factories.CourseRunFactory(course=draft_course, draft=True).update_or_create_official_version()
        publisher_course = publisher_factories.CourseFactory(number='blahx')
        course_team_user_role = publisher_factories.CourseUserRoleFactory(
            course=publisher_course,
            user=self.user_1,
            role=PublisherUserRole.CourseTeam
        )
        self.assertEqual(CourseEditor.objects.count(), 0)
        self.assertEqual(Course.everything.filter(key=course_key).count(), 2)

        self.handle()

        self.assertEqual(CourseEditor.objects.count(), 1)
        editor = CourseEditor.objects.first()
        self.assertEqual(editor.user, self.user_1)
        self.assertEqual(editor.user, course_team_user_role.user)
        self.assertEqual(editor.course, draft_course)

    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_config(self, mock_logger):
        configs = MigrateCourseEditorsConfig.objects.all()
        self.assertEqual(configs.count(), 0)

        try:
            self.handle()
        except CommandError as e:
            self.assertEqual(str(e), 'No organization keys were defined.')
        mock_logger.error.assert_called_with(
            'No organization keys were defined. Please add organization keys to the MigrateCourseEditorsConfig model.'
        )

    @ddt.data('NotARealOrgKey', 'FakeOrg1,FakeOrg2,FakeOrg3')
    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_matched_org_keys(self, org_keys, mock_logger):
        factories.MigrateCourseEditorsConfigFactory(org_keys=org_keys)

        try:
            self.handle()
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
        factories.MigrateCourseEditorsConfigFactory(org_keys=self.org_1.key)
        course_number = '777x'
        factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+' + course_number,
        )
        self.assertEqual(CourseEditor.objects.count(), 0)

        self.handle()

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
        self.assertEqual(editor.course, self.course_1)
