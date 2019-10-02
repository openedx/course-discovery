import mock
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory, SalesforceConfigurationFactory, UserFactory
from course_discovery.apps.course_metadata.management.commands.migrate_comments_to_salesforce import Command
from course_discovery.apps.course_metadata.salesforce import SalesforceUtil
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, MigrateCommentsToSalesforceFactory, OrganizationFactory
)
from course_discovery.apps.publisher.models import Course as PublisherCourse
from course_discovery.apps.publisher.models import CourseRun as PublisherCourseRun
from course_discovery.apps.publisher.tests.factories import CourseFactory as PublisherCourseFactory
from course_discovery.apps.publisher.tests.factories import CourseRunFactory as PublisherCourseRunFactory
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class TestMigrateCommentsToSalesforce(TestCase):
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.migrate_comments_to_salesforce.logger'

    def setUp(self):
        super(TestMigrateCommentsToSalesforce, self).setUp()
        self.partner = PartnerFactory()
        self.user_1 = UserFactory()
        self.org_1 = OrganizationFactory(partner=self.partner)
        self.course_1 = CourseFactory(
            partner=self.partner,
            authoring_organizations=[self.org_1],
            key=self.org_1.key + '+101x',
            title='Old Title',
        )
        self.course_run_1 = CourseRunFactory(
            key='course-v1:{key}+1T2019'.format(
                key=self.course_1.key,
            ),
            course=self.course_1,
        )

        self.publisher_course_1 = PublisherCourseFactory(number='101x', title='New Title')
        self.publisher_course_1.organizations.add(self.org_1)  # pylint: disable=no-member
        self.publisher_course_run_1 = PublisherCourseRunFactory(
            course=self.publisher_course_1,
            lms_course_id='course-v1:{org}+{number}+1T2019'.format(
                org=self.org_1.key, number=self.publisher_course_1.number
            ),
        )

    def tearDown(self):
        super(TestMigrateCommentsToSalesforce, self).tearDown()
        # Zero out the instances that are created during testing
        SalesforceUtil.instances = {}

    @mock.patch(LOGGER_PATH)
    def test_handle_no_orgs(self, mock_logger):
        config = MigrateCommentsToSalesforceFactory()
        config.orgs.all().delete()

        with self.assertRaises(CommandError):
            Command().handle()
        mock_logger.error.assert_called_with(
            'No organizations were defined. Please add organizations to the MigrateCommentsToSalesforce model.'
        )

    @mock.patch(LOGGER_PATH)
    def test_handle_no_partner(self, mock_logger):
        config = MigrateCommentsToSalesforceFactory()
        config.orgs.add(self.org_1)
        with self.assertRaises(CommandError):
            Command().handle()
        mock_logger.error.assert_called_with(
            'No partner was defined. Please add a partner to the MigrateCommentsToSalesforce model.'
        )

    @mock.patch(LOGGER_PATH)
    def test_handle_no_salesforce_configuration(self, mock_logger):
        config = MigrateCommentsToSalesforceFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        with self.assertRaises(CommandError):
            Command().handle()
        mock_logger.error.assert_called_with(
            'Salesforce configuration for {} does not exist'.format(self.partner.name)
        )

    @mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce')
    def test_handle_without_publisher_course_run(self, mock_salesforce):
        config = MigrateCommentsToSalesforceFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        SalesforceConfigurationFactory(partner=self.partner)

        self.publisher_course_run_1.delete()

        # Set return values for all of the Salesforce methods that get called
        mock_salesforce().Publisher_Organization__c.create.return_value = {'id': 'SomePubOrgId'}
        mock_salesforce().Course__c.create.return_value = {'id': 'SomeCourseId'}
        mock_salesforce().Case.create.return_value = {'id': 'SomeCaseId'}
        mock_salesforce().Course_Run__c.create.return_value = {'id': 'SomeCourseRunId'}

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            Command().handle()
            calls = [
                mock.call('No PublisherCourseRun found for {}.'.format(self.course_run_1.key)),
                mock.call('No PublisherCourses found for {}'.format(self.course_1.key))
            ]
            mock_logger.warning.assert_has_calls(calls, any_order=True)

    @mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce')
    def test_handle_with_comments(self, mock_salesforce):
        config = MigrateCommentsToSalesforceFactory(partner=self.partner)
        config.orgs.add(self.org_1)
        SalesforceConfigurationFactory(partner=self.partner)
        course_comment = CommentFactory(
            user=self.user_1,
            content_type_id=ContentType.objects.get_for_model(PublisherCourse),
            object_pk=self.publisher_course_1.id,
        )
        course_comment.content_type_id = ContentType.objects.get_for_model(PublisherCourse)
        course_comment.object_pk = self.publisher_course_1.id
        course_comment.save()

        course_run_comment = CommentFactory(
            user=self.user_1,
            content_type_id=ContentType.objects.get_for_model(PublisherCourseRun),
            object_pk=self.publisher_course_run_1.id,
        )
        course_run_comment.content_type_id = ContentType.objects.get_for_model(PublisherCourseRun)
        course_run_comment.object_pk = self.publisher_course_run_1.id
        course_run_comment.save()

        # Set return values for all of the Salesforce methods that get called
        mock_salesforce().Publisher_Organization__c.create.return_value = {'id': 'SomePubOrgId'}
        mock_salesforce().Course__c.create.return_value = {'id': 'SomeCourseId'}
        mock_salesforce().Case.create.return_value = {'id': 'SomeCaseId'}
        mock_salesforce().Course_Run__c.create.return_value = {'id': 'SomeCourseRunId'}

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            Command().handle()
            self.org_1.refresh_from_db()
            self.course_1.refresh_from_db()
            self.course_run_1.refresh_from_db()

            self.assertEqual(self.org_1.salesforce_id, 'SomePubOrgId')
            self.assertEqual(self.course_1.salesforce_id, 'SomeCourseId')
            self.assertEqual(self.course_1.salesforce_case_id, 'SomeCaseId')
            self.assertEqual(self.course_run_1.salesforce_id, 'SomeCourseRunId')

            mock_logger.info.assert_called_with('Inserted 2 comments for {}'.format(self.course_1.title))
