import datetime
import json
import re
from uuid import uuid4

import ddt
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.template.loader import render_to_string
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from testfixtures import LogCapture, StringComparison

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata import emails
from course_discovery.apps.course_metadata.models import CourseEditor, CourseRunStatus, CourseType
from course_discovery.apps.course_metadata.tests.constants import MOCK_PRODUCTS_DATA
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseFactory, CourseRunFactory, CourseTypeFactory, OrganizationFactory, PartnerFactory,
    SourceFactory
)
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import LEGAL_TEAM_GROUP_NAME
from course_discovery.apps.publisher.tests.factories import (
    GroupFactory, OrganizationExtensionFactory, OrganizationUserRoleFactory, UserAttributeFactory
)


@ddt.ddt
class EmailTests(TestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name='MyOrg', key='myorg')
        self.course_run = CourseRunFactory(draft=True, title_override='MyCourse')
        self.course = self.course_run.course
        self.course.authoring_organizations.add(self.org)
        self.partner = self.course.partner
        self.group = GroupFactory()
        self.pc = self.make_user(email='pc@example.com')
        self.editor = self.make_user(groups=[self.group])
        self.editor2 = self.make_user(groups=[self.group])
        self.non_editor = self.make_user(groups=[self.group])
        self.legal = self.make_user(groups=[Group.objects.get(name=LEGAL_TEAM_GROUP_NAME)])

        CourseEditorFactory(user=self.editor, course=self.course)
        CourseEditorFactory(user=self.editor2, course=self.course)
        OrganizationExtensionFactory(group=self.group, organization=self.org)
        OrganizationUserRoleFactory(user=self.pc, organization=self.org, role=InternalUserRole.ProjectCoordinator.value)

        self.publisher_url = f'{self.partner.publisher_url}courses/{self.course_run.course.uuid}'
        self.studio_url = f'{self.partner.studio_url}course/{self.course_run.key}'
        self.admin_url = 'https://{}/admin/course_metadata/courserun/{}/change/'.format(
            self.partner.site.domain, self.course_run.id
        )
        self.run_num = CourseKey.from_string(self.course_run.key).run

    @staticmethod
    def make_user(groups=None, **kwargs):
        user = UserFactory(**kwargs)
        UserAttributeFactory(user=user, enable_email_notification=True)
        if groups:
            user.groups.set(groups)
        return user

    def assertEmailContains(self, subject=None, to_users=None, both_regexes=None, text_regexes=None,
                            html_regexes=None, index=0):
        email = mail.outbox[index]
        if to_users is not None:
            assert set(email.to) == {u.email for u in to_users}
        if subject is not None:
            self.assertRegex(str(email.subject), subject)
        assert len(email.alternatives) == 1
        assert email.alternatives[0][1] == 'text/html'

        text = email.body
        html = email.alternatives[0][0]

        for regex in both_regexes or []:
            self.assertRegex(text, regex)
            self.assertRegex(html, regex)
        for regex in text_regexes or []:
            self.assertRegex(text, regex)

        for regex in html_regexes or []:
            self.assertRegex(html, regex)

    def assertEmailDoesNotContain(self, both_regexes=None, text_regexes=None, html_regexes=None, index=0):
        email = mail.outbox[index]
        text = email.body
        html = email.alternatives[0][0]

        for regex in both_regexes or []:
            self.assertNotRegex(text, regex)
            self.assertNotRegex(html, regex)

        for regex in text_regexes or []:
            self.assertNotRegex(text, regex)

        for regex in html_regexes or []:
            self.assertNotRegex(html, regex)

    def assertEmailSent(self, function, subject=None, to_users=None, both_regexes=None, text_regexes=None,
                        html_regexes=None, index=0, total=1):
        function(self.course_run)

        assert len(mail.outbox) == total
        self.assertEmailContains(subject=subject, to_users=to_users, both_regexes=both_regexes,
                                 text_regexes=text_regexes, html_regexes=html_regexes, index=index)

    def assertEmailNotSent(self, function, reason):
        with LogCapture(emails.logger.name) as log_capture:
            function(self.course_run)

        assert len(mail.outbox) == 0

        if reason:
            log_capture.check(
                (
                    emails.logger.name,
                    'INFO',
                    StringComparison('Not sending notification email for template course_metadata/email/.* because ' +
                                     re.escape(reason)),
                )
            )

    def test_send_email_for_legal_review(self):
        """
        Verify that send_email_for_legal_review's happy path works as expected
        """
        project_coordinator_2 = self.make_user(email='pc2@test.com')
        OrganizationUserRoleFactory(
            user=project_coordinator_2, organization=self.org, role=InternalUserRole.ProjectCoordinator.value
        )
        self.assertEmailSent(
            emails.send_email_for_legal_review,
            f'^Legal review requested: {self.course_run.title}$',
            [self.legal],
            both_regexes=[
                'Dear legal team,',
                'MyOrg has submitted MyCourse for review.',
                'Note: This email address is unable to receive replies.',
            ],
            html_regexes=[
                '<a href="%s">View this course run in Publisher</a> to determine OFAC status.' % self.publisher_url,
                r'For questions or comments, please contact your Project Coordinator\(s\):',
                '<a href="mailto:pc@example.com">pc@example.com</a>, ',
                '<a href="mailto:pc2@test.com">pc2@test.com</a>',
            ],
            text_regexes=[
                '%s\nView this course run in Publisher above to determine OFAC status.' % self.publisher_url,
                r'For questions or comments, please contact your Project Coordinator\(s\):pc@example.com,pc2@test.com'
            ],
        )

    def test_send_email_to_notify_course_watchers(self):
        """
        Verify that send_email_to_notify_course_watchers's happy path works as expected
        """
        test_course_run = CourseRunFactory(course=self.course, status=CourseRunStatus.Published)
        test_course_run.go_live_date = datetime.datetime.now()
        self.course.watchers = ['test@test.com']
        self.course.save()
        emails.send_email_to_notify_course_watchers(self.course, test_course_run.go_live_date, test_course_run.status)
        email = mail.outbox[0]

        assert email.to == self.course.watchers
        assert str(email.subject) == f'Course URL for {self.course.title}'
        assert len(mail.outbox) == 1
        assert email.alternatives[0][1] == 'text/html'

        expected_content = render_to_string('course_metadata/email/watchers_course_url.html', {
            'is_course_published': True,
            'course_name': self.course.title,
            'course_publish_date': test_course_run.go_live_date.strftime("%m/%d/%Y"),
            'course_marketing_url': self.course.marketing_url,
            'marketing_service_name': settings.MARKETING_SERVICE_NAME,
        })
        # Compare the expected template content with the email body
        assert email.alternatives[0][0] == expected_content

    def test_send_email_for_internal_review(self):
        """
        Verify that send_email_for_internal_review's happy path works as expected
        """
        restricted_url = self.partner.lms_admin_url.rstrip('/') + '/embargo/restrictedcourse/'
        self.assertEmailSent(
            emails.send_email_for_internal_review,
            f'^Review requested: {re.escape(self.course_run.key)} - {self.course_run.title}$',
            [self.pc],
            both_regexes=[
                'Dear Project Coordinator team,',
                'MyOrg has submitted %s for review.' % re.escape(self.course_run.key),
            ],
            html_regexes=[
                '<a href="%s">View this course run in Publisher</a> to review the changes and mark it as reviewed.' %
                self.publisher_url,
                'This is a good time to <a href="%s">review this course run in Studio</a>.' %
                re.escape(self.studio_url),
                'Visit the <a href="%s">restricted course admin page</a> to set embargo rules for this course, '
                'as needed.' % restricted_url,
            ],
            text_regexes=[
                '\n\nPublisher page: %s\n' % self.publisher_url,
                '\n\nStudio page: %s\n' % re.escape(self.studio_url),
                '\n\nRestricted Course admin: %s\n' % restricted_url,
            ],
        )

    def test_send_email_for_reviewed(self):
        """
        Verify that send_email_for_reviewed's happy path works as expected
        """
        self.assertEmailSent(
            emails.send_email_for_reviewed,
            f'^Review complete: {self.course_run.title}$',
            [self.editor, self.editor2],
            both_regexes=[
                'Dear course team,',
                'The course run about page is now published.',
                'Note: This email address is unable to receive replies.',
            ],
            html_regexes=[
                'The <a href="%s">%s course run</a> of %s has been reviewed and approved by %s.' %
                (self.publisher_url, self.run_num, self.course_run.title, settings.PLATFORM_NAME),
                r'For questions or comments, please contact your Project Coordinator\(s\):',
                '<a href="mailto:pc@example.com">pc@example.com</a>',
            ],
            text_regexes=[
                'The %s course run of %s has been reviewed and approved by %s.' %
                (self.run_num, self.course_run.title, settings.PLATFORM_NAME),
                '\n\nView the course run in Publisher: %s\n' % self.publisher_url,
                r'For questions or comments, please contact your Project Coordinator\(s\):pc@example.com'
            ],
        )

    def test_send_email_for_go_live(self):
        """
        Verify that send_email_for_go_live's happy path works as expected
        """
        kwargs = {
            'both_regexes': [
                'The About page for the %s course run of %s has been published.' %
                (self.run_num, self.course_run.title),
                'No further action is necessary.',
            ],
            'html_regexes': [
                '<a href="%s">View this About page.</a>' % self.course_run.marketing_url,
                r'For questions or comments, please contact your Project Coordinator\(s\):',
                '<a href="mailto:pc@example.com">pc@example.com</a>',
            ],
            'text_regexes': [
                '\n\nView this About page. %s\n' % self.course_run.marketing_url,
                r'For questions or comments, please contact your Project Coordinator\(s\):pc@example.com'
            ],
        }

        self.assertEmailSent(
            emails.send_email_for_go_live,
            f'^Published: {self.course_run.title}$',
            [self.editor, self.editor2],
            total=2,
            **kwargs,
        )
        self.assertEmailContains(
            subject=f'^Published: {re.escape(self.course_run.key)} - {self.course_run.title}$',
            to_users=[self.pc],
            index=1,
            **kwargs,
        )

    def test_no_project_coordinator(self):
        """
        Verify that no email is sent and a message is logged if no PC is defined
        """
        self.pc.delete()
        self.assertEmailNotSent(
            emails.send_email_for_internal_review,
            'no project coordinator is defined for organization myorg'
        )

    def test_no_organization(self):
        """
        Verify that no email is sent and a message is logged if no org is defined
        """
        self.org.delete()
        self.assertEmailNotSent(
            emails.send_email_for_internal_review,
            'no organization is defined for course %s' % self.course_run.course.key
        )

    def test_no_publisher_url(self):
        """
        Verify that no email is sent and a message is logged if the publisher_url is missing
        """
        self.partner.publisher_url = None
        self.partner.save()
        self.assertEmailNotSent(
            emails.send_email_for_internal_review,
            'no publisher URL is defined for partner %s' % self.partner.short_code
        )

    def test_no_studio_url(self):
        """
        Verify that no email is sent and a message is logged if the studio_url is missing
        """
        self.partner.studio_url = None
        self.partner.save()
        self.assertEmailNotSent(
            emails.send_email_for_internal_review,
            'no studio URL is defined for partner %s' % self.partner.short_code
        )

    def test_no_lms_admin_url(self):
        """
        Verify that no link is provided to the restricted course admin if we don't have lms_admin_url
        """
        self.partner.lms_admin_url = None
        self.partner.save()
        self.assertEmailSent(emails.send_email_for_internal_review)
        self.assertEmailDoesNotContain(
            both_regexes=[
                re.compile('restricted', re.IGNORECASE),
            ],
        )

    def test_no_editors(self):
        """
        Verify that no reviewed email is sent if no editors exist
        """
        self.editor.delete()
        self.editor2.delete()
        self.non_editor.delete()
        self.assertEmailNotSent(emails.send_email_for_reviewed, None)

    def test_respect_for_no_email_flag(self):
        """
        Verify that no email is sent if the user requests it
        """
        self.editor.attributes.enable_email_notification = False
        self.editor.attributes.save()
        self.assertEmailSent(emails.send_email_for_reviewed, to_users=[self.editor2])

    def test_emails_all_org_users_if_no_editors(self):
        """
        Verify that we send email to all org users if no editors exist
        """
        CourseEditor.objects.all().delete()
        self.assertEmailSent(emails.send_email_for_reviewed, to_users=[self.editor, self.editor2, self.non_editor])

    def test_reviewed_go_live_date_in_future(self):
        """
        Verify that we mention when the course run will go live, if it's in the future
        """
        self.course_run.go_live_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)
        self.assertEmailSent(
            emails.send_email_for_reviewed,
            both_regexes=[
                'The course run about page will be published on %s' % self.course_run.go_live_date.strftime('%x'),
            ],
        )

    def test_reviewed_go_live_date_in_past(self):
        """
        Verify that we mention when the course run is now live, if we missed the go live date
        """
        self.course_run.go_live_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)
        self.assertEmailSent(
            emails.send_email_for_reviewed,
            both_regexes=[
                'The course run about page is now published.',
            ],
        )

    def test_comment_email_sent(self):
        comment = 'This is a test comment'
        emails.send_email_for_comment({
            'user': {
                'username': self.editor.username,
                'email': self.editor.email,
                'first_name': self.editor.first_name,
                'last_name': self.editor.last_name,
            },
            'comment': comment,
            'created': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, self.course, self.editor)

        assert len(mail.outbox) == 1
        self.assertEmailContains(
            both_regexes=[
                f'{self.editor.username} made the following comment on',
                comment
            ],
        )

    @ddt.data(
        ('Executive Education(2U)', CourseType.EXECUTIVE_EDUCATION_2U),
        ('Bootcamp(2U)', CourseType.BOOTCAMP_2U),
    )
    @ddt.unpack
    def test_no_email_sent_for_external_courses(self, type_name, type_slug):
        """
        Verify the editor emails are not sent when the course in question is
        an external course.
        """
        course_type = CourseTypeFactory(
            name=type_name,
            slug=type_slug
        )
        course = CourseFactory(partner=self.partner, title='No email Test', key='edX+bootcamp', type=course_type)
        course.authoring_organizations.add(self.org)
        CourseEditorFactory(user=self.editor, course=course)
        CourseEditorFactory(user=self.editor2, course=course)
        self.course_run.course = course
        self.course_run.status = CourseRunStatus.Published
        # Save method internally sends emails to PCs and editors of the published course.
        # Skipping email send here to explicitly call email method below to emphasize no email to editors
        # is sent for external courses.
        self.course_run.save(send_emails=False)

        with LogCapture(emails.logger.name) as log_capture:
            emails.send_email_to_editors(self.course_run, 'course_metadata/email/go_live', 'Published')

        assert len(mail.outbox) == 0

        log_capture.check(
            (
                emails.logger.name,
                'INFO',
                "Skipping send email to the editors of external course: 'No email Test' with type: '{}'".format(
                    type_slug
                )
            )
        )


@ddt.ddt
class TestIngestionEmail(TestCase):
    """
    Test suite for send_ingestion_email.
    """
    EMAIL_SUBJECT = 'Executive Education Ingestion'
    USER_EMAILS = ['edx@example.com']
    EXEC_ED_PRODUCT = 'EXECUTIVE_EDUCATION'
    BOOTCAMP_PRODUCT = 'BOOTCAMPS'
    PRODUCTS_DATA = MOCK_PRODUCTS_DATA

    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        self.source = SourceFactory(name='edX')

    def _get_base_ingestion_stats(self):
        return {
            'total_products_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'updated_products_count': 0,
            'created_products_count': 0,
            'created_products': [],
            'errors': {}
        }

    def _assert_email_content(self, subject, html_contents):
        email = mail.outbox[0]

        assert email.to == self.USER_EMAILS
        assert str(email.subject) == subject
        assert len(mail.outbox) == 1
        assert len(email.alternatives) == 1
        assert email.alternatives[0][1] == 'text/html'

        html = email.alternatives[0][0]
        for html_content in html_contents:
            self.assertInHTML(html_content, html)

    @ddt.data(
        (BOOTCAMP_PRODUCT, "Bootcamp Ingestion"),
        (EXEC_ED_PRODUCT, "Executive Education Ingestion")
    )
    @ddt.unpack
    def test_product_types(self, product_type, email_subject):
        """
        Verify the email content correctly displays the correct product type.
        """
        emails.send_ingestion_email(
            self.partner, email_subject, self.USER_EMAILS, product_type, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 1,
                'success_count': 1,
                'updated_products_count': 1,
            }
        )
        self._assert_email_content(
            email_subject,
            [
                "<tr><th>Successful Ingestion</th><td>1</td></tr>",
                "<tr><th>Ingestion with Errors </th><td>0</td></tr>",
                "<tr><th>Total data rows</th><td>1</td></tr>",
                # pylint: disable=line-too-long
                f"<p>The data ingestion has been run for product type <strong>{product_type}</strong> and product source <strong>{self.source.name}</strong>. "
                f"See below for the ingestion stats.</p>",
            ]
        )

    def test_email_with_file_attachment(self):
        """
        Verify the email has the file attachment.
        """
        emails.send_ingestion_email(
            self.partner, self.EMAIL_SUBJECT, self.USER_EMAILS, self.EXEC_ED_PRODUCT, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 1,
                'success_count': 1,
                'updated_products_count': 1,
                'products_json': self.PRODUCTS_DATA
            },
        )

        email = mail.outbox[0]
        assert email.attachments is not None
        assert len(email.attachments) == 1
        assert email.attachments[0][0] == 'products.json'
        assert email.attachments[0][1] == json.dumps(self.PRODUCTS_DATA, indent=2)
        assert email.attachments[0][2] == 'application/json'

    def test_email_no_ingestion_failure(self):
        """
        Verify the email content for no ingestion failure.
        """
        emails.send_ingestion_email(
            self.partner, self.EMAIL_SUBJECT, self.USER_EMAILS, self.EXEC_ED_PRODUCT, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 1,
                'success_count': 1,
                'updated_products_count': 1,
            }
        )

        self._assert_email_content(
            self.EMAIL_SUBJECT,
            ["<tr><th>Successful Ingestion</th><td>1</td></tr>",
             "<tr><th>Ingestion with Errors </th><td>0</td></tr>",
             "<tr><th>Total data rows</th><td>1</td></tr>"]
        )

    def test_email_new_products(self):
        """
        Verify the email content for new products.
        """
        uuid = str(uuid4())
        url_slug = 'course-slug-1'
        emails.send_ingestion_email(
            self.partner, self.EMAIL_SUBJECT, self.USER_EMAILS, self.EXEC_ED_PRODUCT, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 1,
                'success_count': 1,
                'created_products_count': 1,
                'created_products': [
                    {
                        'uuid': uuid,
                        'external_course_marketing_type': None,
                        'url_slug': url_slug,
                    }
                ],
            }
        )

        self._assert_email_content(
            self.EMAIL_SUBJECT,
            [
                "<tr><th>Successful Ingestion</th><td> 1 </td></tr>",
                "<tr><th>Total data rows</th><td> 1 </td></tr>",
                "<tr><th>New Products</th><td> 1 </td></tr>",
                "<tr><th>Updated Products</th><td> 0 </td></tr>",
                "<h3>New Products</h3>",
                f"<li><a href='{self.partner.publisher_url}courses/{uuid}'>{uuid}</a> - {url_slug} </li>"
            ]
        )

    def test_email_new_exec_ed_products(self):
        """
        Verify the email content for new exec products with the addition of external_course_marketing_type.
        """
        uuid = str(uuid4())
        url_slug = 'course-slug-1'
        emails.send_ingestion_email(
            self.partner, self.EMAIL_SUBJECT, self.USER_EMAILS, self.EXEC_ED_PRODUCT, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 3,
                'success_count': 3,
                'created_products_count': 3,
                'created_products': [
                    {
                        'uuid': uuid,
                        'external_course_marketing_type': 'sprint',
                        'url_slug': url_slug,
                    },
                    {
                        'uuid': uuid,
                        'external_course_marketing_type': 'course_stack',
                        'url_slug': url_slug,
                    },
                    {
                        'uuid': uuid,
                        'external_course_marketing_type': 'short_course',
                        'url_slug': url_slug,
                    },
                ],
            }
        )

        self._assert_email_content(
            self.EMAIL_SUBJECT,
            [
                "<tr><th>Successful Ingestion</th><td> 3 </td></tr>",
                "<tr><th>Total data rows</th><td> 3 </td></tr>",
                "<tr><th>New Products</th><td> 3 </td></tr>",
                "<tr><th>Updated Products</th><td> 0 </td></tr>",
                "<h3>New Products</h3>",
                f"<li><a href='{self.partner.publisher_url}courses/{uuid}'>{uuid}</a> - {url_slug} "
                f"(sprint) </li>"
                f"<li><a href='{self.partner.publisher_url}courses/{uuid}'>{uuid}</a> - {url_slug} "
                f"(course_stack) </li>"
                f"<li><a href='{self.partner.publisher_url}courses/{uuid}'>{uuid}</a> - {url_slug} "
                f"(short_course) </li>"
            ]
        )

    def test_email_ingestion_failures(self):
        """
        Verify the email content for the ingestion failures.
        """
        emails.send_ingestion_email(
            self.partner, self.EMAIL_SUBJECT, self.USER_EMAILS, self.EXEC_ED_PRODUCT, self.source,
            {
                **self._get_base_ingestion_stats(),
                'total_products_count': 1,
                'failure_count': 1,
                'errors': {
                    'MISSING_ORGANIZATION': [
                        '[MISSING_ORGANIZATION] Unable to find organization with key edx1'
                    ]
                }
            }
        )

        self._assert_email_content(
            self.EMAIL_SUBJECT,
            [
                "<tr><th>Total data rows</th><td> 1 </td></tr>",
                "<tr><th>Successful Ingestion</th><td> 0 </td></tr>",
                "<tr><th>Ingestion with Errors</th><td> 1 </td></tr>",
                "<h3>Ingestion Failures</h3>",
                "<li>[MISSING_ORGANIZATION] Unable to find organization with key edx1</li>"
            ]
        )


class TestSlugUpdatesEmail(TestCase):
    """
    Test suite for slugs_update email
    """
    EMAIL_SUBJECT = 'Migrate Course Slugs Summary Report'
    USER_EMAILS = ['edx@example.com']

    def test_send_email_for_slug_updates(self):
        slugs_summary_data = [{
            'course_uuid': 'uuid-text',
            'old_slug': 'course-title',
            'new_slug': 'learn/subject/organization-course-title',
            'error': 'some error'
        }]
        stats = 'course_uuid,old_url_slug,new_url_slug,error_msg\n'
        for slug in slugs_summary_data:
            stats += f"{slug['course_uuid']},{slug['old_slug']},{slug['new_slug']},{slug['error']}\n"

        emails.send_email_for_slug_updates(stats, self.USER_EMAILS)
        email = mail.outbox[0]

        assert email.to == self.USER_EMAILS
        assert str(email.subject) == self.EMAIL_SUBJECT
        assert len(mail.outbox) == 1
        expected_response = 'Please find the attached csv file for the summary of course slugs update.'
        assert email.body == expected_response

        assert email.attachments is not None
        assert len(email.attachments) == 1
        assert email.attachments[0].get_filename() == 'slugs_update_summary.csv'
        assert email.attachments[0].get_content_type() == 'text/csv'
        assert email.attachments[0].get_payload() == stats
