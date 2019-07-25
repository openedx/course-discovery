import datetime

import ddt
import mock
from django.core.management import CommandError
from django.db import IntegrityError
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
        self.publisher_course_run_1 = publisher_factories.CourseRunFactory(
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
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
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
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1, org_2)
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
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
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

    def test_handle_orders_by_modified(self):
        """
        If there are two Publisher Courses with the same Course Number and Org, we want to
        prefer the Course that has been modified last when pushing to course metadata.

        This scenario can happen when we remap a course run because of an incorrect course number
        to the course with the correct course number so the course run's number does
        not match with the course number.
        """
        publisher_course_2 = publisher_factories.CourseFactory(
            number=self.publisher_course_1.number,
            title='Newer Title',
            modified=self.publisher_course_1.modified + datetime.timedelta(days=1),
        )
        publisher_course_2.organizations.add(self.org_1)  # pylint: disable=no-member
        publisher_factories.CourseRunFactory(
            course=publisher_course_2,
            lms_course_id='course-v1:{org}+{number}+1T2019'.format(
                org=self.org_1.key, number='102x'
            ),
        )
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        self.assertEqual(self.course_1.title, 'Old Title')

        Command().handle()

        draft_course = Course.everything.get(key=self.course_1.key, draft=True)
        self.assertEqual(draft_course.title, publisher_course_2.title)

        publisher_course_3 = publisher_factories.CourseFactory(
            number=self.publisher_course_1.number,
            title='Newest Title',
            modified=self.publisher_course_1.modified + datetime.timedelta(days=10),
        )
        publisher_course_3.organizations.add(self.org_1)  # pylint: disable=no-member
        publisher_factories.CourseRunFactory(
            course=publisher_course_3,
            lms_course_id='course-v1:{org}+{number}+1T2019'.format(
                org=self.org_1.key, number='103x'
            ),
        )

        Command().handle()

        draft_course.refresh_from_db()
        self.assertEqual(draft_course.title, publisher_course_3.title)

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
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(org)

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

    def test_pub_course_pointing_at_two_metadata_courses(self):
        """
        If a publisher course has two runs that each have their own CM courses, stitch them up right.

        [Publisher] Course 101x has two course runs, 101x+1T2019 and 102x+1T2019. Course 102x does not exist.
        [Course Metadata] Course 101x has one course run 101x+1T2019 and Course 102x has one course run
            102x+1T2019.
        """
        key_2 = 'course-v1:{org}+{number}+1T2019'.format(org=self.org_1.key, number='102x')
        publisher_run_2 = publisher_factories.CourseRunFactory(course=self.publisher_course_1, lms_course_id=key_2)
        run_1 = factories.CourseRunFactory(course=self.course_1, key=self.publisher_course_run_1.lms_course_id,
                                           max_effort=1234)
        course_2 = factories.CourseFactory(partner=self.partner, key=self.org_1.key + '+102x', title="CM Course 2")
        run_2 = factories.CourseRunFactory(course=course_2, key=key_2, max_effort=12345)

        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        Command().handle()

        draft_1 = CourseRun.everything.get(key=run_1.key, draft=True)
        draft_2 = CourseRun.everything.get(key=run_2.key, draft=True)
        self.course_1.refresh_from_db()
        course_2.refresh_from_db()

        # Confirm that we found the right ones, we copied the data over, and their courses are correct
        assert draft_1.course == self.course_1.draft_version
        assert draft_2.course == course_2.draft_version
        assert draft_1.max_effort == self.publisher_course_run_1.max_effort
        assert draft_2.max_effort == publisher_run_2.max_effort

    def test_pub_course_pointing_at_wrong_course_number(self):
        """
        If a publisher course wants to point to a CM course with a different number, stitch them up right.

        This is a real situation from PCs trying to help course teams rename course numbers.

        [Publisher] Course 101x has two course runs, 101x+1T2019 and 102x+1T2019. Course 102x does not exist.
        [Course Metadata] Course 101x has no runs, while 102x has both course runs 101x+1T2019 and 102x+1T2019.
        """
        key_2 = 'course-v1:{org}+{number}+1T2019'.format(org=self.org_1.key, number='102x')
        publisher_run_2 = publisher_factories.CourseRunFactory(course=self.publisher_course_1, lms_course_id=key_2)
        course_2 = factories.CourseFactory(partner=self.partner, key=self.org_1.key + '+102x', title="CM Course 2")
        run_1 = factories.CourseRunFactory(course=course_2, key=self.publisher_course_run_1.lms_course_id,
                                           max_effort=1234)
        run_2 = factories.CourseRunFactory(course=course_2, key=key_2, max_effort=12345)

        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        Command().handle()

        draft_1 = CourseRun.everything.get(key=run_1.key, draft=True)
        draft_2 = CourseRun.everything.get(key=run_2.key, draft=True)
        course_2.refresh_from_db()

        # Confirm that we found the right ones, we copied the data over, and their courses are correct
        assert draft_1.course == course_2.draft_version
        assert draft_2.course == course_2.draft_version
        assert draft_1.max_effort == self.publisher_course_run_1.max_effort
        assert draft_2.max_effort == publisher_run_2.max_effort

    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_config(self, mock_logger):
        self.assertEqual(MigratePublisherToCourseMetadataConfig.objects.count(), 0)

        try:
            Command().handle()
        except CommandError as e:
            self.assertEqual(str(e), 'No organizations were defined.')
        mock_logger.error.assert_called_with(
            'No organizations were defined. Please add organizations to the '
            'MigratePublisherToCourseMetadataConfig model.'
        )

    @mock.patch(LOGGER_PATH)
    def test_handle_with_publish_to_course_metadata_error(self, mock_logger):
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        error_keys = [self.publisher_course_run_1.lms_course_id]

        with mock.patch(
            'course_discovery.apps.course_metadata.management.commands.'
            'migrate_publisher_to_course_metadata.publish_to_course_metadata', side_effect=IntegrityError
        ):
            try:
                Command().handle()
            except CommandError as e:
                self.assertEqual(
                    str(e), 'The following Publisher course run keys failed to publish to '
                            'Course Metadata: {error_keys}.'.format(error_keys=error_keys)
                )

        mock_logger.exception.assert_called_with(
            'Error publishing course run [{course_run_key}] to Course Metadata: {error}. '
            'This may have caused the corresponding course to not be published as well.'.format(
                course_run_key=self.publisher_course_run_1.lms_course_id, error=''
            )
        )

    @mock.patch(LOGGER_PATH)
    def test_handle_with_no_matched_publisher_course(self, mock_logger):
        config = factories.MigratePublisherToCourseMetadataConfigFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        course_number = '777x'
        factories.CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+' + course_number,
            draft=True,
        )
        self.assertEqual(CourseEditor.objects.count(), 0)

        Command().handle()

        mock_logger.info.assert_any_call(
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
