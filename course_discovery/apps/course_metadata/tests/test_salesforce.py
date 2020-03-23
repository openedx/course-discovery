import ddt
import mock
from django.test import TestCase
from simple_salesforce import SalesforceExpiredSession

from course_discovery.apps.core.tests.factories import SalesforceConfigurationFactory, UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun  # pylint: disable=unused-import
from course_discovery.apps.course_metadata.salesforce import (
    SalesforceMissingCaseException, SalesforceNotConfiguredException, SalesforceUtil,
    populate_official_with_existing_draft, requires_salesforce_update
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseFactoryNoSignals, CourseRunFactory, CourseRunFactoryNoSignals, OrganizationFactoryNoSignals
)


@ddt.ddt
class TestSalesforce(TestCase):
    def setUp(self):
        super(TestSalesforce, self).setUp()
        self.salesforce_config = SalesforceConfigurationFactory()
        self.salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        self.salesforce_util_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil'

    def tearDown(self):
        super().tearDown()
        # Zero out the instances that are created during testing
        SalesforceUtil.instances = {}

    def test_login(self):
        # Update the config to reflect what we'll run locally
        self.salesforce_config.security_token = ''
        self.salesforce_config.save()

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch('course_discovery.apps.course_metadata.salesforce.requests') as mock_requests:
                SalesforceUtil(self.salesforce_config.partner)
                mock_salesforce.assert_called_with(
                    session=mock_requests.Session(),
                    **{
                        'username': self.salesforce_config.username,
                        'password': self.salesforce_config.password,
                        'organizationId': self.salesforce_config.organization_id,
                        'security_token': '',
                        'domain': 'test',
                    }
                )

    def test_wrapper_salesforce_expired_session_calls_login(self):
        """
        Tests the wrapper when a SalesforceExpiredSession is thrown.
        The first exception thrown will trigger a re-login, the second will
        throw an exception as we don't want infinite retries.
        """
        course = CourseFactoryNoSignals(
            partner=self.salesforce_config.partner,
            salesforce_id='TestSalesforceId',
            salesforce_case_id='TestSalesforceCaseId',
        )

        with mock.patch(
            self.salesforce_util_path + '._query',
            side_effect=SalesforceExpiredSession(url='Test', status=401, resource_name='Test', content='Test')
        ):
            with mock.patch(self.salesforce_path) as mock_salesforce:
                util = SalesforceUtil(self.salesforce_config.partner)
                # Any method that has the decorator
                with self.assertRaises(SalesforceExpiredSession):
                    util.get_comments_for_course(course)
                # 2 calls, one for initialization, one for login before exception
                self.assertEqual(len(mock_salesforce.call_args_list), 2)

    def test_wrapper_salesforce_os_error_calls_login(self):
        """
        Tests the wrapper when an OSError exception is thrown.
        The first exception thrown will trigger a re-login, the second will
        throw an exception as we don't want infinite retries.
        """
        course = CourseFactoryNoSignals(
            partner=self.salesforce_config.partner,
            salesforce_id='TestSalesforceId',
            salesforce_case_id='TestSalesforceCaseId',
        )

        with mock.patch(self.salesforce_util_path + '._query', side_effect=OSError('Test Error')):
            with mock.patch(self.salesforce_path) as mock_salesforce:
                with mock.patch('course_discovery.apps.course_metadata.salesforce.logger') as mock_logger:
                    util = SalesforceUtil(self.salesforce_config.partner)
                    # Any method that has the decorator
                    with self.assertRaises(OSError):
                        util.get_comments_for_course(course)
                    # 2 calls, one for initialization, one for login before exception
                    self.assertEqual(len(mock_salesforce.call_args_list), 2)
                    mock_logger.warning.assert_called_with(
                        'An OSError occurred while attempting to call get_comments_for_course'
                    )

    def test_wrapper_salesforce_without_client_raises_not_configured_exception(self):
        """
        Tests the wrapper when no config is found but a query is run
        """
        course = CourseFactoryNoSignals(
            partner=self.salesforce_config.partner,
            salesforce_id='TestSalesforceId',
            salesforce_case_id='TestSalesforceCaseId',
        )
        with mock.patch(self.salesforce_path):
            util = SalesforceUtil(self.salesforce_config.partner)
            SalesforceUtil.instances[self.salesforce_config.partner].client = None
            # Any method that has the decorator
            with self.assertRaises(SalesforceNotConfiguredException):
                util.get_comments_for_course(course)

    def test_singleton(self):
        new_config = SalesforceConfigurationFactory()
        with mock.patch(self.salesforce_path):
            # Instantiate these twice for the same partner, verify only one instance is created each
            SalesforceUtil(self.salesforce_config.partner)
            SalesforceUtil(self.salesforce_config.partner)
            SalesforceUtil(new_config.partner)
            SalesforceUtil(new_config.partner)
        self.assertEqual(len(SalesforceUtil.instances), 2)

    def test_soql_escape(self):
        with mock.patch(self.salesforce_path):
            util = SalesforceUtil(self.salesforce_config.partner)
            escaped_string = util.soql_escape(r"Some 'test' \string")
            self.assertEqual(
                escaped_string,
                r"Some \'test\' \\string",
            )

    def test_create_account_salesforce_id_set(self):
        organization = OrganizationFactoryNoSignals(
            key='edX', partner=self.salesforce_config.partner, salesforce_id='Test'
        )

        with mock.patch(self.salesforce_path) as mock_salesforce:
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_publisher_organization(organization)

            mock_salesforce().Publisher_Organization__c.create.assert_not_called()

    def test_create_account_salesforce_id_not_set(self):
        organization = OrganizationFactoryNoSignals(key='edX', partner=self.salesforce_config.partner)

        return_value = {
            'id': 'SomeSalesforceId'
        }

        with mock.patch(self.salesforce_path) as mock_salesforce:
            mock_salesforce().Publisher_Organization__c.create.return_value = return_value
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_publisher_organization(organization)
            mock_salesforce().Publisher_Organization__c.create.assert_called_with({
                'Organization_Name__c': organization.name,
                'Organization_Key__c': organization.key,
            })
            self.assertEqual(organization.salesforce_id, return_value.get('id'))

    def test_create_course_salesforce_id_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='Test')

        with mock.patch(self.salesforce_path) as mock_salesforce:
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_course(course)
            mock_salesforce().Course__c.create.assert_not_called()

    def test_create_course_salesforce_id_not_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner)
        organization = OrganizationFactoryNoSignals(
            key='edX', partner=self.salesforce_config.partner, salesforce_id='Test'
        )
        course.authoring_organizations.add(organization)
        partner = self.salesforce_config.partner

        return_value = {
            'id': 'SomeSalesforceId'
        }

        with mock.patch(self.salesforce_path) as mock_salesforce:
            mock_salesforce().Course__c.create.return_value = return_value
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_course(course)
            mock_salesforce().Course__c.create.assert_called_with({
                'Course_Name__c': course.title,
                'Link_to_Publisher__c': '{url}/courses/{uuid}'.format(
                    url=partner.publisher_url.strip('/'), uuid=course.uuid
                ) if partner.publisher_url else None,
                'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/course/{id}/change/'.format(
                    url=partner.site.domain.strip('/'), id=course.id
                ) if partner.site.domain else None,
                'Course_Key__c': course.key,
                'Publisher_Organization__c': organization.salesforce_id,
            })
            self.assertEqual(course.salesforce_id, return_value.get('id'))

    def test_create_course_organization_salesforce_id_not_set(self):
        create_pub_org_path = (self.salesforce_util_path + '.create_publisher_organization')

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner)
        organization = OrganizationFactoryNoSignals(key='edX', partner=self.salesforce_config.partner)
        course.authoring_organizations.add(organization)
        partner = self.salesforce_config.partner

        return_value = {
            'id': 'SomeSalesforceId'
        }

        # Need to modify state of the instance passed in
        def new_create_organization(self, instance):  # pylint: disable=unused-argument
            instance.salesforce_id = 'SomeSalesforceId'
            instance.save()

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(create_pub_org_path, new=new_create_organization):
                mock_salesforce().Course__c.create.return_value = return_value
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertIsNone(organization.salesforce_id)
                util.create_course(course)
                organization.refresh_from_db()
                mock_salesforce().Course__c.create.assert_called_with({
                    'Course_Name__c': course.title,
                    'Link_to_Publisher__c': '{url}/courses/{uuid}'.format(
                        url=partner.publisher_url.strip('/'), uuid=course.uuid
                    ) if partner.publisher_url else None,
                    'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/course/{id}/change/'.format(
                        url=partner.site.domain.strip('/'), id=course.id
                    ) if partner.site.domain else None,
                    'Course_Key__c': course.key,
                    'Publisher_Organization__c': organization.salesforce_id,
                })

                self.assertIsNotNone(organization.salesforce_id)
                self.assertEqual(course.salesforce_id, return_value.get('id'))

    def test_create_course_run_salesforce_id_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='Test')
        course_run = CourseRunFactoryNoSignals(course=course, salesforce_id='Test')

        with mock.patch(self.salesforce_path) as mock_salesforce:
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_course_run(course_run)
            mock_salesforce().Course_Run__c.create.assert_not_called()

    def test_create_course_run_salesforce_id_not_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='TestSalesforceId')
        course_run = CourseRunFactoryNoSignals(course=course)
        partner = self.salesforce_config.partner

        return_value = {
            'id': 'SomeSalesforceId'
        }

        with mock.patch(self.salesforce_path) as mock_salesforce:
            mock_salesforce().Course_Run__c.create.return_value = return_value
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_course_run(course_run)
            mock_salesforce().Course_Run__c.create.assert_called_with({
                'Course__c': course_run.course.salesforce_id,
                'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/courserun/{id}/change/'.format(
                    url=partner.site.domain.strip('/'), id=course_run.id
                ),
                'Course_Start_Date__c': course_run.start.isoformat(),
                'Course_End_Date__c': course_run.end.isoformat(),
                'Publisher_Status__c': 'Live',  # Expected return value from _get_equivalent_status
                'Course_Run_Name__c': course_run.title,
                'Expected_Go_Live_Date__c': None,
                'Course_Number__c': course_run.key,
                # Expected return value from _get_equivalent_ofac_review_decision
                'OFAC_Review_Decision__c': 'OFAC Enabled',
            })
            self.assertEqual(course_run.salesforce_id, return_value.get('id'))

    def test_create_course_run_course_salesforce_id_not_set(self):
        create_course_path = self.salesforce_util_path + '.create_course'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner)
        course_run = CourseRunFactoryNoSignals(course=course)
        partner = self.salesforce_config.partner

        return_value = {
            'id': 'SomeSalesforceId'
        }

        # Need to modify state of the instance passed in
        def new_create_course(self, instance):  # pylint: disable=unused-argument
            instance.salesforce_id = 'SomeSalesforceId'
            instance.save()

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(create_course_path, new=new_create_course):
                mock_salesforce().Course_Run__c.create.return_value = return_value
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertIsNone(course.salesforce_id)
                util.create_course_run(course_run)
                mock_salesforce().Course_Run__c.create.assert_called_with({
                    'Course__c': course_run.course.salesforce_id,
                    'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/courserun/{id}/change/'.format(
                        url=partner.site, id=course_run.id
                    ),
                    'Course_Start_Date__c': course_run.start.isoformat(),
                    'Course_End_Date__c': course_run.end.isoformat(),
                    'Publisher_Status__c': 'Live',  # Expected return value from _get_equivalent_status
                    'Course_Run_Name__c': course_run.title,
                    'Expected_Go_Live_Date__c': None,
                    'Course_Number__c': course_run.key,
                    # Expected return value from _get_equivalent_ofac_review_decision
                    'OFAC_Review_Decision__c': 'OFAC Enabled',
                })
            self.assertIsNotNone(course.salesforce_id)
            self.assertEqual(course_run.salesforce_id, return_value.get('id'))

    def test_create_case_for_course_salesforce_case_id_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_case_id='Test')

        with mock.patch(self.salesforce_path) as mock_salesforce:
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_case_for_course(course)
            mock_salesforce().Case.create.assert_not_called()

    def test_create_case_for_course_salesforce_case_id_not_set_salesforce_id_set(self):
        course = CourseFactoryNoSignals(
            partner=self.salesforce_config.partner,
            salesforce_id='TestSalesforceId',
        )
        official_course = CourseFactoryNoSignals(
            partner=self.salesforce_config.partner,
            draft_version=course,
        )

        return_value = {
            'id': 'SomeSalesforceId'
        }

        with mock.patch(self.salesforce_path) as mock_salesforce:
            mock_salesforce().Case.create.return_value = return_value
            util = SalesforceUtil(self.salesforce_config.partner)
            util.create_case_for_course(course)
            mock_salesforce().Case.create.assert_called_with({
                'Course__c': course.salesforce_id,
                'Status': 'Open',
                'Origin': 'Publisher',
                'Subject': '{} Comments'.format(course.title),
                'Description': 'This case is required to be Open for the Publisher comment service.',
                'RecordTypeId': self.salesforce_config.case_record_type_id,
            })
            self.assertEqual(course.salesforce_case_id, return_value.get('id'))
            self.assertEqual(official_course.salesforce_case_id, return_value.get('id'))

    def test_create_case_for_course_salesforce_case_id_not_set_salesforce_id_not_set(self):
        create_course_path = self.salesforce_util_path + '.create_course'

        self.salesforce_config.case_record_type_id = 'TestId'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner)

        return_value = {
            'id': 'SomeSalesforceId'
        }

        # Need to modify state of the instance passed in
        def new_create_course(self, instance):  # pylint: disable=unused-argument
            instance.salesforce_id = 'SomeSalesforceId'
            instance.save()

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(create_course_path, new=new_create_course):
                mock_salesforce().Case.create.return_value = return_value
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertIsNone(course.salesforce_id)
                util.create_case_for_course(course)
                mock_salesforce().Case.create.assert_called_with({
                    'Course__c': course.salesforce_id,
                    'Status': 'Open',
                    'Origin': 'Publisher',
                    'Subject': '{} Comments'.format(course.title),
                    'Description': 'This case is required to be Open for the Publisher comment service.',
                    'RecordTypeId': self.salesforce_config.case_record_type_id,
                })
                self.assertIsNotNone(course.salesforce_id)
                self.assertEqual(course.salesforce_case_id, return_value.get('id'))

    def test_create_comment_for_course_case_salesforce_case_id_set(self):
        create_case_path = self.salesforce_util_path + '.create_case_for_course'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_case_id='TestSalesforceId')
        user = UserFactory()

        body = 'Test body'

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(create_case_path) as mock_create_case_for_course:
                util = SalesforceUtil(self.salesforce_config.partner)
                util.create_comment_for_course_case(course, user, body)
                mock_salesforce().FeedItem.create.assert_called_with({
                    'ParentId': course.salesforce_case_id,
                    'Body': util.format_user_comment_body(user, body, None)
                })
                mock_create_case_for_course.assert_not_called()

    def test_create_comment_for_course_case_salesforce_case_id_not_set(self):
        create_case_path = self.salesforce_util_path + '.create_case_for_course'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='TestSalesforceId')
        user = UserFactory()

        body = 'Test body'

        # Need to modify state of the instance passed in
        def new_create_course_case(self, instance):  # pylint: disable=unused-argument
            instance.salesforce_case_id = 'SomeSalesforceId'
            instance.save()

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(create_case_path, new=new_create_course_case):
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertIsNone(course.salesforce_case_id)
                util.create_comment_for_course_case(course, user, body)
                mock_salesforce().FeedItem.create.assert_called_with({
                    'ParentId': course.salesforce_case_id,
                    'Body': util.format_user_comment_body(user, body, None)
                })
                self.assertIsNotNone(course.salesforce_case_id)

    def test_create_comment_for_course_case_raises_exceptions(self):
        create_case_path = self.salesforce_util_path + '.create_case_for_course'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='TestSalesforceId')
        user = UserFactory()

        body = 'Test body'

        # Need to modify state of the instance passed in and make it None to simulate an error
        def new_create_course_case(self, instance):  # pylint: disable=unused-argument
            instance.salesforce_case_id = None
            instance.save()

        with mock.patch(self.salesforce_path):
            with mock.patch(create_case_path, new=new_create_course_case):
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertIsNone(course.salesforce_case_id)
                with self.assertRaises(SalesforceMissingCaseException):
                    util.create_comment_for_course_case(course, user, body)

    def test_get_comments_for_course_case_id_not_set(self):
        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id='TestSalesforceId')

        with mock.patch(self.salesforce_path):
            util = SalesforceUtil(self.salesforce_config.partner)
            comments = util.get_comments_for_course(course)
            self.assertEqual(comments, [])

    def test_get_comments_for_course_case_id_set(self):
        user = UserFactory()
        query_path = self.salesforce_util_path + '._query'

        course = CourseFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_case_id='TestSalesforceId')

        return_value = {
            'records': [
                {
                    'CreatedBy': {
                        'Username': user.username
                    },
                    'CreatedDate': '2000-01-01',
                    'Body': ('[User]\n{}\n\n'
                                   '[Course Run]\ncourse-v1:testX+TestX+Test\n\n'
                                   '[Body]\nThis is a formatted test message.').format(user.username),
                },
                {
                    'CreatedBy': {
                        'Username': 'internal'
                    },
                    'CreatedDate': '2000-01-01',
                    'Body': 'This is an internal user comment without formatting.'
                },
            ]
        }

        with mock.patch(self.salesforce_path):
            with mock.patch(query_path, return_value=return_value) as mock_query:
                util = SalesforceUtil(self.salesforce_config.partner)
                comments = util.get_comments_for_course(course)
                mock_query.assert_called_with(
                    "SELECT CreatedDate,Body,CreatedBy.Username,CreatedBy.Email,CreatedBy.FirstName,CreatedBy.LastName "
                    "FROM FeedItem WHERE ParentId='{}' AND IsDeleted=FALSE ORDER BY CreatedDate ASC".format(
                        course.salesforce_case_id
                    )
                )
                self.assertEqual(comments, [
                    {
                        'user': {
                            'username': user.username,
                            'email': user.email,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                        },
                        'course_run_key': 'course-v1:testX+TestX+Test',
                        'comment': 'This is a formatted test message.',
                        'created': '2000-01-01',
                    },
                    {
                        'user': {
                            'username': 'internal',
                            'email': None,
                            'first_name': None,
                            'last_name': None,
                        },
                        'course_run_key': None,
                        'comment': 'This is an internal user comment without formatting.',
                        'created': '2000-01-01',
                    },
                ])

    def test_format_and_parse(self):
        user = UserFactory()
        body = 'This is a test body.'
        course_run_key = 'course-v1:testX+TestX+Test'

        with mock.patch(self.salesforce_path):
            util = SalesforceUtil(self.salesforce_config.partner)
            formatted_message = util.format_user_comment_body(user, body, course_run_key)
            expected_formatted_message = '[User]\n{}\n\n[Course Run]\n{}\n\n[Body]\n{}'.format(
                '{} {} ({})'.format(user.first_name, user.last_name, user.username), course_run_key, body
            )
            self.assertEqual(
                formatted_message,
                expected_formatted_message
            )
            parsed_message = util._parse_user_comment_body(  # pylint: disable=protected-access
                {
                    'Body': formatted_message
                }
            )
            parsed_user = parsed_message.get('user')
            self.assertEqual(parsed_user.get('username'), user.username)
            # Below 3 will always be None for a matched comment
            self.assertEqual(parsed_user.get('email'), None)
            self.assertEqual(parsed_user.get('first_name'), None)
            self.assertEqual(parsed_user.get('last_name'), None)

            self.assertEqual(parsed_message.get('course_run_key'), course_run_key)
            self.assertEqual(parsed_message.get('comment'), body)
            user.first_name = ''
            user.last_name = ''
            user.save()

            formatted_message = util.format_user_comment_body(user, body, course_run_key)
            expected_formatted_message = '[User]\n{}\n\n[Course Run]\n{}\n\n[Body]\n{}'.format(
                '{}'.format(user.username), course_run_key, body
            )
            self.assertEqual(
                formatted_message,
                expected_formatted_message
            )

    @ddt.data('test-id', None)
    def test_update_publisher_organization(self, salesforce_id):
        """Test Cases: updating organization with a salesforce_id, with no salesforce_id"""
        organization = OrganizationFactoryNoSignals(partner=self.salesforce_config.partner, salesforce_id=salesforce_id)

        with mock.patch(self.salesforce_path) as mock_salesforce:
            util = SalesforceUtil(self.salesforce_config.partner)
            util.update_publisher_organization(organization)
            if salesforce_id:
                mock_salesforce().Publisher_Organization__c.update.assert_called()
            else:
                mock_salesforce().Publisher_Organization__c.update.assert_not_called()

    @ddt.data('test-id', None)
    def test_update_course(self, salesforce_id):
        """Test Cases: updating course with a salesforce_id, with no salesforce_id"""
        course = CourseFactory()
        course.salesforce_id = salesforce_id

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(self.salesforce_util_path + '.create_course') as mock_create:
                util = SalesforceUtil(self.salesforce_config.partner)
                util.update_course(course)
                if salesforce_id:
                    mock_salesforce().Course__c.update.assert_called()
                else:
                    mock_salesforce().Course__c.update.assert_not_called()
                    mock_create.assert_called()

    @ddt.data('test-id', None)
    def test_update_course_run(self, salesforce_id):
        """Test Cases: updating course run with a salesforce_id, with no salesforce_id"""
        course_run = CourseRunFactory()
        course_run.salesforce_id = salesforce_id

        with mock.patch(self.salesforce_path) as mock_salesforce:
            with mock.patch(self.salesforce_util_path + '.create_course_run') as mock_create:
                util = SalesforceUtil(self.salesforce_config.partner)
                util.update_course_run(course_run)
                if salesforce_id:
                    mock_salesforce().Course_Run__c.update.assert_called()
                else:
                    mock_salesforce().Course_Run__c.update.assert_not_called()
                    mock_create.assert_called()

    def test_requires_salesforce_update(self):
        org = OrganizationFactoryNoSignals(partner=self.salesforce_config.partner)
        org.description = 'changed'
        self.assertEqual(requires_salesforce_update('organization', org), False)

        org.name = 'changed'
        self.assertEqual(requires_salesforce_update('organization', org), True)

        course = CourseFactory()
        course.short_description = 'changed'
        self.assertEqual(requires_salesforce_update('course', course), False)

        course.title = 'changed'
        self.assertEqual(requires_salesforce_update('course', course), True)

        course_run = CourseRunFactory()
        course_run.full_description = 'changed'
        self.assertEqual(requires_salesforce_update('course_run', course_run), False)

        course_run.key = 'changed'
        self.assertEqual(requires_salesforce_update('course_run', course_run), True)

    def test_populate_official_with_existing_draft(self):
        course_run = CourseRunFactory(draft=True, course=CourseFactory(draft=True))
        course_run.status = CourseRunStatus.Reviewed
        course_run.save()

        salesforce_id = 'SomeSalesforceId'

        course_run_2 = CourseRunFactory(
            draft=True,
            course=CourseFactory(
                draft=True,
                salesforce_id=salesforce_id
            ),
            salesforce_id=salesforce_id
        )
        course_run_2.status = CourseRunStatus.Reviewed
        course_run_2.save()

        # Need to modify state of the instance passed in
        def new_create_instance(instance):
            instance.salesforce_id = salesforce_id
            instance.save()

        with mock.patch(
                'course_discovery.apps.course_metadata.tests.test_salesforce.CourseRun.save'
        ):
            with mock.patch(
                    'course_discovery.apps.course_metadata.tests.test_salesforce.Course.save'
            ):
                with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
                    with mock.patch(self.salesforce_util_path + '.create_course_run', new=new_create_instance):
                        with mock.patch(self.salesforce_util_path + '.create_course', new=new_create_instance):
                            created = populate_official_with_existing_draft(
                                course_run.official_version, mock_salesforce_util
                            )
                            self.assertTrue(created)
                            self.assertEqual(course_run.official_version.salesforce_id, salesforce_id)

                            created = populate_official_with_existing_draft(
                                course_run.official_version.course, mock_salesforce_util
                            )
                            self.assertTrue(created)
                            self.assertEqual(course_run.official_version.course.salesforce_id, salesforce_id)

                            created = populate_official_with_existing_draft(
                                course_run_2.official_version, mock_salesforce_util
                            )
                            self.assertFalse(created)
                            self.assertEqual(course_run_2.official_version.salesforce_id, salesforce_id)

                            created = populate_official_with_existing_draft(
                                course_run_2.official_version.course, mock_salesforce_util
                            )
                            self.assertFalse(created)
                            self.assertEqual(course_run_2.official_version.course.salesforce_id, salesforce_id)
