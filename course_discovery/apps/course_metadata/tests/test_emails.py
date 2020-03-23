import datetime
import re

from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from testfixtures import LogCapture, StringComparison

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata import emails
from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseRunFactory, OrganizationFactory
)
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import LEGAL_TEAM_GROUP_NAME
from course_discovery.apps.publisher.tests.factories import (
    GroupFactory, OrganizationExtensionFactory, OrganizationUserRoleFactory, UserAttributeFactory
)


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
        OrganizationUserRoleFactory(user=self.pc, organization=self.org, role=InternalUserRole.ProjectCoordinator)

        self.publisher_url = '{}courses/{}'.format(self.partner.publisher_url, self.course_run.course.uuid)
        self.studio_url = '{}course/{}'.format(self.partner.studio_url, self.course_run.key)
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
            self.assertEqual(set(email.to), {u.email for u in to_users})
        if subject is not None:
            self.assertRegex(str(email.subject), subject)
        self.assertEqual(len(email.alternatives), 1)
        self.assertEqual(email.alternatives[0][1], 'text/html')

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

        self.assertEqual(len(mail.outbox), total)
        self.assertEmailContains(subject=subject, to_users=to_users, both_regexes=both_regexes,
                                 text_regexes=text_regexes, html_regexes=html_regexes, index=index)

    def assertEmailNotSent(self, function, reason):
        with LogCapture(emails.logger.name) as log_capture:
            function(self.course_run)

        self.assertEqual(len(mail.outbox), 0)

        if reason:
            log_capture.check(
                (
                    emails.logger.name,
                    'INFO',
                    StringComparison('Not sending notification email for template course_metadata/email/.* because ' +
                                     reason),
                )
            )

    def test_send_email_for_legal_review(self):
        """
        Verify that send_email_for_legal_review's happy path works as expected
        """
        self.assertEmailSent(
            emails.send_email_for_legal_review,
            '^Legal review requested: {}$'.format(self.course_run.title),
            [self.legal],
            both_regexes=[
                'Dear legal team,',
                'MyOrg has submitted MyCourse for review.',
                'Note: This email address is unable to receive replies.',
            ],
            html_regexes=[
                '<a href="%s">View this course run in Publisher</a> to determine OFAC status.' % self.publisher_url,
                'For questions or comments, please contact '
                '<a href="mailto:pc@example.com">the Project Coordinator</a>.',
            ],
            text_regexes=[
                '%s\nView this course run in Publisher above to determine OFAC status.' % self.publisher_url,
                'For questions or comments, please contact the Project Coordinator at pc@example.com.',
            ],
        )

    def test_send_email_for_internal_review(self):
        """
        Verify that send_email_for_internal_review's happy path works as expected
        """
        restricted_url = self.partner.lms_admin_url.rstrip('/') + '/embargo/restrictedcourse/'
        self.assertEmailSent(
            emails.send_email_for_internal_review,
            '^Review requested: {} - {}$'.format(self.course_run.key, self.course_run.title),
            [self.pc],
            both_regexes=[
                'Dear %s,' % self.pc.full_name,
                'MyOrg has submitted %s for review.' % self.course_run.key,
            ],
            html_regexes=[
                '<a href="%s">View this course run in Publisher</a> to review the changes and mark it as reviewed.' %
                self.publisher_url,
                'This is a good time to <a href="%s">review this course run in Studio</a>.' % self.studio_url,
                'Visit the <a href="%s">restricted course admin page</a> to set embargo rules for this course, '
                'as needed.' % restricted_url,
            ],
            text_regexes=[
                '\n\nPublisher page: %s\n' % self.publisher_url,
                '\n\nStudio page: %s\n' % self.studio_url,
                '\n\nRestricted Course admin: %s\n' % restricted_url,
            ],
        )

    def test_send_email_for_reviewed(self):
        """
        Verify that send_email_for_reviewed's happy path works as expected
        """
        self.assertEmailSent(
            emails.send_email_for_reviewed,
            '^Review complete: {}$'.format(self.course_run.title),
            [self.editor, self.editor2],
            both_regexes=[
                'Dear course team,',
                'The course run about page is now published.',
                'Note: This email address is unable to receive replies.',
            ],
            html_regexes=[
                'The <a href="%s">%s course run</a> of %s has been reviewed and approved by %s.' %
                (self.publisher_url, self.run_num, self.course_run.title, settings.PLATFORM_NAME),
                'For questions or comments, please contact '
                '<a href="mailto:pc@example.com">your Project Coordinator</a>.',
            ],
            text_regexes=[
                'The %s course run of %s has been reviewed and approved by %s.' %
                (self.run_num, self.course_run.title, settings.PLATFORM_NAME),
                '\n\nView the course run in Publisher: %s\n' % self.publisher_url,
                'For questions or comments, please contact your Project Coordinator at pc@example.com.',
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
                'For questions or comments, please contact '
                '<a href="mailto:pc@example.com">your Project Coordinator</a>.',
            ],
            'text_regexes': [
                '\n\nView this About page. %s\n' % self.course_run.marketing_url,
                'For questions or comments, please contact your Project Coordinator at pc@example.com.',
            ],
        }

        self.assertEmailSent(
            emails.send_email_for_go_live,
            '^Published: {}$'.format(self.course_run.title),
            [self.editor, self.editor2],
            total=2,
            **kwargs,
        )
        self.assertEmailContains(
            subject='^Published: {} - {}$'.format(self.course_run.key, self.course_run.title),
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

        self.assertEqual(len(mail.outbox), 1)
        self.assertEmailContains(
            both_regexes=[
                '{} made the following comment on'.format(self.editor.username),
                comment
            ],
        )
