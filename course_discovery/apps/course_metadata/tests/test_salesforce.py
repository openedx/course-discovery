import mock
from django.test import TestCase
from simple_salesforce import SalesforceExpiredSession

from course_discovery.apps.core.tests.factories import SalesforceConfigurationFactory
from course_discovery.apps.course_metadata.salesforce import SalesforceUtil
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, OrganizationFactory


class TestSalesforce(TestCase):
    def setUp(self):
        super(TestSalesforce, self).setUp()
        self.salesforce_config = SalesforceConfigurationFactory()

    def tearDown(self):
        # Zero out the instances that are created during testing
        SalesforceUtil.instances = {}

    def test_login(self):
        # Update the config to reflect what we'll run locally
        self.salesforce_config.security_token = ''
        self.salesforce_config.save()

        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce') as mock_salesforce:
            SalesforceUtil(self.salesforce_config.partner)
            mock_salesforce.assert_called_with(**{
                'username': self.salesforce_config.username,
                'password': self.salesforce_config.password,
                'organizationId': self.salesforce_config.organization_id,
                'security_token': '',
                'domain': 'test',
            })

    def test_wrapper_salesforce_expired_session_calls_login(self):
        """
        Tests the wrapper when a SalesforceExpiredSession exception is thrown every query.
        The first exception thrown will trigger a re-login, the second will
        throw an exception as we don't want infinite retries.
        """
        with mock.patch(
            'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
            side_effect=SalesforceExpiredSession(url='Test', status=401, resource_name='Test', content='Test')
        ):
            with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce') as mock_salesforce:
                util = SalesforceUtil(self.salesforce_config.partner)
                # Any method that has the decorator
                with self.assertRaises(SalesforceExpiredSession):
                    util.get_account_by_key('Test')
                    # 2 calls, one for initialization, one for login before exception
                    mock_salesforce.assert_num_calls(2)

    def test_singleton(self):
        new_config = SalesforceConfigurationFactory()
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            # Instantiate these twice for the same partner, verify only one instance is created each
            SalesforceUtil(self.salesforce_config.partner)
            SalesforceUtil(self.salesforce_config.partner)
            SalesforceUtil(new_config.partner)
            SalesforceUtil(new_config.partner)
        self.assertEqual(len(SalesforceUtil.instances), 2)

    def test_soql_escape(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            util = SalesforceUtil(self.salesforce_config.partner)
            escaped_string = util.soql_escape(r"Some 'test' \string")
            self.assertEqual(
                escaped_string,
                r"Some \'test\' \\string",
            )

    def test_get_account_by_key(self):
        return_value = 'A record'
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={'records': [return_value]}
            ) as mock_query:
                util = SalesforceUtil(self.salesforce_config.partner)
                accounts = util.get_account_by_key('Test')
                mock_query.assert_called_with('SELECT Id,Name FROM Account WHERE Name=Test')
                self.assertEqual(accounts, return_value)

    def test_get_account_by_key_exception(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={}
            ):
                util = SalesforceUtil(self.salesforce_config.partner)
                with self.assertRaises(Exception):
                    util.get_account_by_key('Test')

    def test_get_course_by_course_key(self):
        return_value = 'A record'
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={'records': [return_value]}
            ) as mock_query:
                util = SalesforceUtil(self.salesforce_config.partner)
                accounts = util.get_course_by_course_key('Test')
                query_string = 'SELECT Id,Name,Course_Number__c,Account__c FROM Course__c WHERE Course_Number__c=Test'
                mock_query.assert_called_with(query_string)
                self.assertEqual(accounts, return_value)

    def test_get_course_by_course_key_exception(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={}
            ):
                util = SalesforceUtil(self.salesforce_config.partner)
                with self.assertRaises(Exception):
                    util.get_course_by_course_key('Test')

    def test_get_course_run_by_name(self):
        return_value = 'A record'
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={'records': [return_value]}
            ) as mock_query:
                util = SalesforceUtil(self.salesforce_config.partner)
                accounts = util.get_course_run_by_name('Test')
                query_string = (
                    'SELECT Id,Course_Run_Name__c,Course_Run_Number__c,Parent_Course_Name__c ' +
                    'FROM Course_Runs__c WHERE Course_Run_Number__c=Test'
                )
                mock_query.assert_called_with(query_string)
                self.assertEqual(accounts, return_value)

    def test_get_course_run_by_name_exception(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={}
            ):
                util = SalesforceUtil(self.salesforce_config.partner)
                with self.assertRaises(Exception):
                    util.get_course_run_by_name('Test')

    def test_get_case_by_salesforce_course_id(self):
        return_value = 'A record'
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={'records': [return_value]}
            ) as mock_query:
                util = SalesforceUtil(self.salesforce_config.partner)
                accounts = util.get_case_by_salesforce_course_id('Test')
                query_string = 'SELECT Id,Course__c,Subject FROM Case WHERE Course__c=Test'

                mock_query.assert_called_with(query_string)
                self.assertEqual(accounts, return_value)

    def test_get_case_by_salesforce_course_id_exception(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(
                'course_discovery.apps.course_metadata.salesforce.SalesforceUtil._query',
                return_value={}
            ):
                util = SalesforceUtil(self.salesforce_config.partner)
                with self.assertRaises(Exception):
                    util.get_case_by_salesforce_course_id('Test')

    def test_get_or_create_course_run_new(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_course_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_or_create_course'
        get_course_run_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_course_run_by_name'

        course_run = CourseRunFactory(course__partner=self.salesforce_config.partner)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(create_course_path, return_value=return_value):
                with mock.patch(get_course_run_path, return_value=None):
                    util = SalesforceUtil(self.salesforce_config.partner)
                    util.get_or_create_course_run(course_run)
                    mock_salesforce().Course_Runs__c.create.assert_called_with({
                        'Course_Run_Name__c': course_run.title,
                        'Course_Run_Number__c': course_run.key,
                        'Parent_course_name__c': return_value.get('Id'),
                    })

    def test_get_or_create_course_run_found(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        get_course_run_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_course_run_by_name'

        course_run = CourseRunFactory(course__partner=self.salesforce_config.partner)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(get_course_run_path, return_value=return_value):
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertEqual(util.get_or_create_course_run(course_run), return_value)
                mock_salesforce().Course_Runs__c.create.assert_not_called()

    def test_get_or_create_course_new(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_account_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_or_create_account'
        get_course_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_course_by_course_key'

        course = CourseFactory(partner=self.salesforce_config.partner)
        org = OrganizationFactory(key='edX', partner=self.salesforce_config.partner)
        course.authoring_organizations.add(org)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(create_account_path, return_value=return_value) as mock_create_account:
                with mock.patch(get_course_path, return_value=None):
                    util = SalesforceUtil(self.salesforce_config.partner)
                    util.get_or_create_course(course)
                    mock_create_account.assert_called_with(account_key=org.key)
                    mock_salesforce().Course__c.create.assert_called_with({
                        'Name': course.title,
                        'Course_Number__c': course.key,
                        'Account__c': return_value.get('Id'),
                    })

    def test_get_or_create_course_found(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        get_course_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_course_by_course_key'

        course = CourseFactory(partner=self.salesforce_config.partner)
        org = OrganizationFactory(key='edX', partner=self.salesforce_config.partner)
        course.authoring_organizations.add(org)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(get_course_path, return_value=return_value):
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertEqual(util.get_or_create_course(course), return_value)
                mock_salesforce().Course__c.create.assert_not_called()

    def test_get_or_create_case_new(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_course_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_or_create_course'
        get_case_path = (
            'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_case_by_salesforce_course_id'
        )

        course = CourseFactory(partner=self.salesforce_config.partner)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(create_course_path, return_value=return_value):
                with mock.patch(get_case_path, return_value=None):
                    util = SalesforceUtil(self.salesforce_config.partner)
                    util.get_or_create_case(course)
                    mock_salesforce().Case.create.assert_called_with({
                        'Course__c': return_value.get('Id'),
                        'Subject': '{} comments'.format(course.title),
                    })

    def test_get_or_create_case_found(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_course_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_or_create_course'
        get_case_path = (
            'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_case_by_salesforce_course_id'
        )

        course = CourseFactory(partner=self.salesforce_config.partner)
        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(get_case_path, return_value=return_value):
                with mock.patch(create_course_path, return_value=return_value):
                    util = SalesforceUtil(self.salesforce_config.partner)
                    self.assertEqual(util.get_or_create_course(course), return_value)
                    mock_salesforce().Course__c.create.assert_not_called()

    def test_get_or_create_account_new(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        get_account_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_account_by_key'

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(get_account_path, return_value=None):
                util = SalesforceUtil(self.salesforce_config.partner)
                util.get_or_create_account('Test')
                mock_salesforce().Account.create.assert_called_with({
                    'Name': 'Test',
                })

    def test_get_or_create_account_found(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        get_account_path = 'course_discovery.apps.course_metadata.salesforce.SalesforceUtil.get_account_by_key'

        return_value = {'Id': 'Test'}

        with mock.patch(salesforce_path) as mock_salesforce:
            with mock.patch(get_account_path, return_value=return_value):
                util = SalesforceUtil(self.salesforce_config.partner)
                self.assertEqual(util.get_or_create_account('Test'), return_value)
                mock_salesforce().Account.create.assert_not_called()
