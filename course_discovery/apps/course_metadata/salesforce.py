import re

from simple_salesforce import Salesforce, SalesforceExpiredSession

from course_discovery.apps.publisher.choices import PublisherUserRole


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
        client = None

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

    def _query(self, soql, *soql_args):
        return self.client.query(soql.format(*[self.soql_escape(arg) for arg in soql_args]))

    def soql_escape(self, soql):
        """
        Escapes a soql string against injection

        The single quote and backlash characters are reserved in SOQL
        queries and must be preceded by a backslash to be properly interpreted.
        """
        return soql.replace('\\', r'\\').replace("'", r"\'")

    @salesforce_request_wrapper
    def create_publisher_organization(self, organization):
        if not organization.salesforce_id:
            sf_organization = self.client.Publisher_Organization__c.create({
                'Organization_Name__c': organization.name,
                'Organization_Key__c': organization.key,
            })
            organization.salesforce_id = sf_organization.get('id')
            organization.save()

    @salesforce_request_wrapper
    def create_course(self, course):
        if not course.salesforce_id:
            organization = course.authoring_organizations.first()
            if organization and not organization.salesforce_id:
                self.create_publisher_organization(organization)
            sf_course = self.client.Course__c.create({
                'Course_Name__c': course.title,
                'Link_to_Publisher__c': '{url}/courses/{uuid}'.format(
                    url=self.partner.publisher_url, uuid=course.uuid
                ) if self.partner.publisher_url else None,
                'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/course/{id}/change/'.format(
                    url=self.partner.site.domain, id=course.id
                ) if self.partner.site.domain else None,
                'Publisher_Status__c': None,
                'OFAC_Review_Decision__c': course.has_ofac_restrictions,
                'Project_Coordinator__c': organization.organization_user_roles.filter(
                    role=PublisherUserRole.ProjectCoordinator
                ).first() or None if organization else None,
                'Course_Key__c': course.key,
            })
            course.salesforce_id = sf_course.get('id')
            course.save()

    @salesforce_request_wrapper
    def create_course_run(self, course_run):
        if not course_run.salesforce_id:
            if not course_run.course.salesforce_id:
                self.create_course(course_run.course)
            sf_course_run = self.client.Course_Run__c.create({
                'Course__c': course_run.course.salesforce_id,
                'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/courserun/{id}/change/'.format(
                    url=self.partner.site, id=course_run.id
                ),
                'Course_Start_Date__c': course_run.end.isoformat(),
                'Course_Run_Date__c': course_run.end.isoformat(),
                'Publisher_Status__c': course_run.status,
                'Course_Run_Name__c': course_run.title,
                'Expected_Go_Live_Date__c': course_run.go_live_date,
            })
            course_run.salesforce_id = sf_course_run.get('id')
            course_run.save()

    @salesforce_request_wrapper
    def create_case_for_course(self, course):
        if not course.salesforce_case_id:
            if not course.salesforce_id:
                self.create_course(course)
            case = {
                'Course__c': course.salesforce_id,
                'Status': 'Open',
                'Origin': 'Publisher',
                'Subject': '{} Comments'.format(course.title),
                'Description': 'This case is required to be Open for the Publisher comment service.'
            }
            case_record_type_id = self.partner.salesforce.case_record_type_id
            # Only add the record type ID if it's configured, this is not a required field
            if case_record_type_id:
                case['RecordTypeId'] = case_record_type_id

            sf_case = self.client.Case.create(case)
            course.salesforce_case_id = sf_case.get('id')
            course.save()

    @salesforce_request_wrapper
    def create_comment_for_course_case(self, course, user, body, course_run_key=None):
        if not course.salesforce_case_id:
            self.create_case_for_course(course)
        self.client.CaseComment.create({
            'ParentId': course.salesforce_case_id,
            'CommentBody': self._format_user_comment_body(user, body, course_run_key),
        })

    @staticmethod
    def _format_user_comment_body(user, body, course_run_key=None):
        if user.first_name and user.last_name:
            user_message = '[User]\n{first_name} {last_name} ({email})'.format(
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
            )
        else:
            user_message = '[User]\n{email}'.format(email=user.email)
        course_run_message = '[Course Run]\n{course_run_key}\n\n'.format(
            course_run_key=course_run_key
        ) if course_run_key else ''
        return '{user_message}\n\n{course_run_message}[Body]\n{body}'.format(
            user_message=user_message,
            course_run_message=course_run_message,
            body=body,
        )

    @salesforce_request_wrapper
    def get_comments_for_course(self, course):
        if course.salesforce_case_id:
            fields = [
                'CreatedDate',
                'CommentBody',
                'CreatedBy.Email',
            ]
            comments = self._query(
                "SELECT {} FROM CaseComment WHERE ParentId='{}' AND IsDeleted=FALSE ORDER BY CreatedDate ASC".format(
                    ','.join(fields),
                    course.salesforce_case_id,
                )
            )
            parsed_comments = [self._parse_user_comment_body(comment) for comment in comments.get('records')]
            return parsed_comments
        return []

    @staticmethod
    def _parse_user_comment_body(comment):
        match = re.match(
            r"\[User\]\n?(?:^(?:.*\s\(?)?(.+@[\w\.\-]+)\)?$\n\n)(?:\[Course Run\]\n^(.+)$\n\n)?\[Body\]\n^(.+)",
            comment.get('CommentBody'),
            flags=re.MULTILINE
        )
        if match:
            return {
                'email': match.groups()[0],
                'course_run': match.groups()[1],
                'comment': match.groups()[2],
            }
        return {
            'email': comment.get('CreatedBy').get('Email'),
            'course_run': None,
            'comment': comment.get('CommentBody'),
        }
