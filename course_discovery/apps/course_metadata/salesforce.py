import re
from datetime import datetime, timezone

from simple_salesforce import Salesforce, SalesforceExpiredSession

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.choices import CourseRunStatus


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
                    url=self.partner.publisher_url.strip('/') if self.partner.publisher_url else '', uuid=course.uuid
                ),
                'Link_to_Admin_Portal__c': '{url}/admin/course_metadata/course/{id}/change/'.format(
                    url=self.partner.site.domain.strip('/') if self.partner.site.domain else '', id=course.id
                ),
                'OFAC_Review_Decision__c': course.has_ofac_restrictions,
                'Course_Key__c': course.key,
                'Publisher_Organization__c': organization.salesforce_id if organization else None,
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
                    url=self.partner.site.domain.strip('/') if self.partner.site.domain else '', id=course_run.id
                ),
                'Course_Start_Date__c': course_run.start.isoformat() if course_run.start else None,
                'Course_End_Date__c': course_run.end.isoformat() if course_run.end else None,
                'Publisher_Status__c': self._get_salesforce_equivalent(course_run.status),
                'Course_Run_Name__c': course_run.title,
                'Expected_Go_Live_Date__c': course_run.go_live_date.isoformat() if course_run.go_live_date else None,
                'Course_Number__c': course_run.key,
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
        user_comment_body = self.format_user_comment_body(user, body, course_run_key=course_run_key)
        self.client.FeedItem.create({
            'ParentId': course.salesforce_case_id,
            'Body': user_comment_body,
        })
        return self._create_comment_return_body(user, body, course_run_key)

    @staticmethod
    def format_user_comment_body(user, body, course_run_key=None):
        if user.first_name and user.last_name:
            user_message = '[User]\n{first_name} {last_name} ({username})'.format(
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
            )
        else:
            user_message = '[User]\n{username}'.format(username=user.username)
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
                'Body',
                'CreatedBy.Username',
                'CreatedBy.Email',
                'CreatedBy.FirstName',
                'CreatedBy.LastName',
            ]
            comments = self._query(
                "SELECT {} FROM FeedItem WHERE ParentId='{}' AND IsDeleted=FALSE ORDER BY CreatedDate ASC".format(
                    ','.join(fields),
                    course.salesforce_case_id,
                )
            )
            # FeedItems.Body cannot be part of a WHERE clause because it is a TextArea type.
            # When Cases are created empty Body FeedItems are as well (Case Created, Owner Assigned)
            # so we filter these empty Body results out so as to not display them as "Comments"
            filtered_comment_records = [comment for comment in comments.get('records') if comment.get('Body')]
            parsed_comments = [self._parse_user_comment_body(comment) for comment in filtered_comment_records]
            comments = self._add_user_info_to_comments(parsed_comments)
            return comments
        return []

    @staticmethod
    def _parse_user_comment_body(comment):
        match = re.match(
            r"\[User\]\n?(?:^(?:.*\s\(?)?(.+?)\)?$\n\n)(?:\[Course Run\]\n^(.+)$\n\n)?\[Body\]\n^(.+)",
            str(comment.get('Body')),
            flags=re.MULTILINE
        )
        if match:
            return {
                'user': {
                    'username': match.groups()[0],
                    'email': None,
                    'first_name': None,
                    'last_name': None,
                },
                'course_run_key': match.groups()[1],
                'comment': match.groups()[2],
                'created': comment.get('CreatedDate'),
            }
        created_by = comment.get('CreatedBy')
        return {
            'user': {
                'username': created_by.get('Username'),
                'email': created_by.get('Email') or None,
                'first_name': created_by.get('FirstName') or None,
                'last_name': created_by.get('LastName') or None,
            },
            'course_run_key': None,
            'comment': comment.get('Body'),
            'created': comment.get('CreatedDate'),
        }

    @staticmethod
    def _add_user_info_to_comments(comments):
        usernames = set()
        for comment in comments:
            user = comment.get('user')
            if user:
                username = user.get('username')
                if username:
                    usernames.add(username)
        users = User.objects.filter(username__in=usernames)
        users = {user.username: user for user in users}
        for comment in comments:
            # Treat not having a first_name as a trigger to get the User from Publisher
            comment_user = comment.get('user')
            username = comment_user.get('username')
            if comment_user and username and not comment_user.get('first_name'):
                user = users.get(username)
                if user:
                    comment['user']['email'] = user.email or None
                    comment['user']['first_name'] = user.first_name or None
                    comment['user']['last_name'] = user.last_name or None
        return comments

    @staticmethod
    def _create_comment_return_body(user, body, course_run_key=None):
        """
        Salesforce does not return the fully created Object, this method
        creates the equivalent of what we would expect to return from our API
        """
        return {
            'user': {
                'username': user.username,
                'email': user.email or None,
                'first_name': user.first_name or None,
                'last_name': user.last_name or None,
            },
            'course_run_key': course_run_key,
            'comment': body,
            'created': datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _get_salesforce_equivalent(status):
        # Note: these must match the equivalent 'picklistValues' for Salesforce's Course_Run__c.Publisher_Status__c
        salesforce_statuses = {
            CourseRunStatus.Unpublished: 'New/Unsubmitted Edits',
            CourseRunStatus.LegalReview: 'In Legal Review',
            CourseRunStatus.InternalReview: 'In PC Review',
            CourseRunStatus.Reviewed: 'Scheduled',
            CourseRunStatus.Published: 'Live',
        }
        return salesforce_statuses.get(status)
