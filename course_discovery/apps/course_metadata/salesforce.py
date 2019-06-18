from simple_salesforce import Salesforce, SalesforceExpiredSession


def salesforce_request_wrapper(method):
    """
    Annotation for querying against Salesforce. Will handle re-authorization if
    the session is logged out, and raise exceptions for unsupported cases.
    """
    def inner(self, *args, **kwargs):
        if self.enabled:
            if self.client:
                try:
                    return method(self, *args, **kwargs)
                except SalesforceExpiredSession:
                    self.login()
                    return method(self, *args, **kwargs)
            raise SalesforceUtil.SalesforceNotConfiguredException(
                'Attempted to query Salesforce with no client for partner={}'.format(self.partner.name)
            )
        raise SalesforceUtil.SalesforceNotConfiguredException(
            'Attempted to query Salesforce with no configuration set up for partner={}'.format(self.partner.name)
        )
    return inner


class SalesforceUtil:
    """
    Singleton utility class to instantiate only a single Salesforce session based on the partner.
    Any and all queries against Salesforce should be wrapped with the salesforce_request_wrapper
    annotation to handle misconfigurations and session timeouts. Any attribute gets fall down to an
    underlying child object which wraps a simple-salesforce connection.
    """

    class SalesforceNotEnabledException(Exception):
        """
        Exception to be raised if the configuration of Salesforce does not exist,
        but an attempt is still made to query for data from within Salesforce
        """
        pass

    class __SalesforceUtil:
        def __init__(self, partner):
            self.partner = partner
            if self.salesforce_is_enabled():
                self.client = self.login()

        def salesforce_is_enabled(self):
            return bool(self.partner.salesforce)

        def login(self):
            salesforce_config = self.partner.salesforce
            sf_kwargs = {
                'username': salesforce_config.username,
                'password': salesforce_config.password,
                'organizationId': salesforce_config.organization_id,
                # security_token must be an empty string if organizationId is set
                'security_token': '' if salesforce_config.organization_id else salesforce_config.token,
                'domain': 'test' if salesforce_config.is_sandbox else ''
            }
            return Salesforce(**sf_kwargs)

    instances = {}

    def __init__(self, partner):
        self.partner = partner
        if partner not in SalesforceUtil.instances:
            SalesforceUtil.instances[partner] = SalesforceUtil.__SalesforceUtil(partner)

    def __getattr__(self, name):
        return getattr(SalesforceUtil.instances.get(self.partner), name)

    @property
    def enabled(self):
        return self.salesforce_is_enabled()

    def _query(self, soql):
        return self.client.query(self.soql_escape(soql))

    def soql_escape(self, soql):
        """
        Escapes a soql string against injection

        The single quote and backlash characters are reserved in SOQL
        queries and must be preceded by a backslash to be properly interpreted.
        """
        return soql.replace('\\', r'\\').replace("'", r"\'")

    @salesforce_request_wrapper
    def get_or_create_account(self, account_key):
        salesforce_account = self.get_account_by_key(account_key)
        # Only create the account if it doesn't already exist
        if not salesforce_account:
            return self.client.Account.create({
                'Name': account_key,
            })
        return salesforce_account

    @salesforce_request_wrapper
    def get_account_by_key(self, name):
        fields = [
            'Id',
            'Name',
        ]
        accounts = self._query('SELECT {} FROM Account WHERE Name={}'.format(','.join(fields), name))
        account_records = accounts.get('records', [])
        if len(account_records) == 1:
            return account_records[0]
        raise Exception('{} records found for Name={}. Expected 1.'.format(len(account_records), name))

    @salesforce_request_wrapper
    def get_or_create_course(self, course):
        salesforce_course = self.get_course_by_course_key(course.key)
        # Only create the Course if it doesn't already exist
        if not salesforce_course:
            account_key = course.authoring_organizations.first().key
            # TODO: Check to see if first() is okay
            account = self.get_or_create_account(account_key=account_key)
            return self.client.Course__c.create({
                'Name': course.title,
                'Course_Number__c': course.key,
                'Account__c': account.get('Id'),
            })
        return salesforce_course

    @salesforce_request_wrapper
    def get_course_by_course_key(self, course_key):
        fields = [
            'Id',
            'Name',
            'Course_Number__c',
            'Account__c',
        ]
        courses = self._query('SELECT {} FROM Course__c WHERE Course_Number__c={}'.format(','.join(fields), course_key))
        course_records = courses.get('records', [])
        if len(course_records) == 1:
            return course_records[0]
        raise Exception('{} records found for Name={}. Expected 1.'.format(len(course_records), course_key))

    @salesforce_request_wrapper
    def get_or_create_course_run(self, course_run):
        salesforce_course_run = self.get_course_run_by_name(course_run.key)
        # Only create the Course Run if it doesn't already exist
        if not salesforce_course_run:
            course = self.get_or_create_course(course_run.course)
            return self.client.Course_Runs__c.create({
                'Course_Run_Name__c': course_run.title,
                'Course_Run_Number__c': course_run.key,
                'Parent_course_name__c': course.get('Id'),
            })
        return salesforce_course_run

    @salesforce_request_wrapper
    def get_course_run_by_name(self, key):
        fields = [
            'Id',
            'Course_Run_Name__c',
            'Course_Run_Number__c',
            'Parent_Course_Name__c',
        ]
        course_runs = self._query(
            'SELECT {} FROM Course_Runs__c WHERE Course_Run_Number__c={}'.format(','.join(fields), key)
        )
        course_run_records = course_runs.get('records', [])
        if len(course_run_records) == 1:
            return course_run_records[0]
        raise Exception('{} records found for Key={}. Expected 1.'.format(len(course_run_records), key))

    @salesforce_request_wrapper
    def get_or_create_case(self, course):
        salesforce_course = self.get_or_create_course(course)
        salesforce_case = self.get_case_by_salesforce_course_id(salesforce_course.get('Id'))
        # Only create the Case if it doesn't already exist
        if not salesforce_case:
            return self.client.Case.create({
                'Course__c': salesforce_course.get('Id'),
                'Subject': '{} comments'.format(course.title)
            })
        return salesforce_case

    def get_case_by_salesforce_course_id(self, salesforce_course_id):
        fields = [
            'Id',
            'Course__c',
            'Subject',
        ]
        case = self._query(
            'SELECT {} FROM Case WHERE Course__c={}'.format(','.join(fields), salesforce_course_id)
        )
        case_records = case.get('records', [])
        if len(case_records) == 1:
            return case_records[0]
        raise Exception('{} records found for Key={}. Expected 1.'.format(len(case_records), salesforce_course_id))
