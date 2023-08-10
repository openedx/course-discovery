import datetime
from unittest import mock

import factory
from django.db.models.signals import m2m_changed, post_save
from rest_framework.reverse import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, SalesforceConfigurationFactory, UserFactory
from course_discovery.apps.course_metadata.salesforce import SalesforceMissingCaseException, SalesforceUtil
from course_discovery.apps.course_metadata.tests.factories import CourseFactoryNoSignals, OrganizationFactoryNoSignals


class CommentViewSetTests(OAuth2Mixin, APITestCase):

    @factory.django.mute_signals(m2m_changed)
    def setUp(self):
        super().setUp()
        self.salesforce_config = SalesforceConfigurationFactory(partner=self.partner)
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.request.site.partner = self.partner
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.course = CourseFactoryNoSignals(partner=self.partner, title='Fake Test', key='edX+Fake101', draft=True)
        self.org = OrganizationFactoryNoSignals(key='edX', partner=self.partner)
        self.course.authoring_organizations.add(self.org)

    def tearDown(self):
        super().tearDown()
        # Zero out the instances that are created during testing
        SalesforceUtil.instances = {}

    def test_list_no_salesforce_case_id_set(self):
        user_orgs_path = 'course_discovery.apps.course_metadata.models.Organization.user_organizations'

        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            with mock.patch(user_orgs_path, return_value=[self.org]):
                url = '{}?course_uuid={}'.format(reverse('api:v1:comment-list'), self.course.uuid)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, [])

    def test_list_salesforce_case_id_set(self):
        self.course.salesforce_id = 'TestSalesforceId'
        with factory.django.mute_signals(post_save):
            self.course.save()

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        get_comments_path = 'course_discovery.apps.api.v1.views.comments.SalesforceUtil.get_comments_for_course'
        user_orgs_path = 'course_discovery.apps.course_metadata.models.Organization.user_organizations'
        return_value = [
            {
                'user': {
                    'first_name': 'TestFirst',
                    'last_name': 'TestLast',
                    'email': 'test@test.com',
                    'username': 'test',
                },
                'course_run_key': None,
                'created': '2000-01-01T00:00:00.000+0000',
                'comment': 'This is a test comment',
            }
        ]
        with mock.patch(salesforce_path):
            with mock.patch(user_orgs_path, return_value=[self.org]):
                with mock.patch(get_comments_path, return_value=return_value) as mock_get_comments:
                    url = '{}?course_uuid={}'.format(reverse('api:v1:comment-list'), self.course.uuid)
                    response = self.client.get(url)
                    mock_get_comments.assert_called_with(self.course)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, return_value)

    def test_list_400s_without_course_uuid(self):
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            url = reverse('api:v1:comment-list')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 400)

    def test_list_404s_without_finding_course(self):
        fake_uuid = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'  # Needs to resemble a uuid to pass validation
        with mock.patch('course_discovery.apps.course_metadata.salesforce.Salesforce'):
            url = '{}?course_uuid={}'.format(reverse('api:v1:comment-list'), fake_uuid)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_list_403s_without_permissions(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        user_orgs_path = 'course_discovery.apps.course_metadata.models.Organization.user_organizations'
        self.user.is_staff = False
        self.user.save()

        with mock.patch(salesforce_path):
            with mock.patch(user_orgs_path, return_value=[]):
                url = '{}?course_uuid={}'.format(reverse('api:v1:comment-list'), self.course.uuid)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)

    def test_list_200s_as_staff(self):
        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        user_orgs_path = 'course_discovery.apps.course_metadata.models.Organization.user_organizations'

        with mock.patch(salesforce_path):
            with mock.patch(user_orgs_path, return_value=[]):
                url = '{}?course_uuid={}'.format(reverse('api:v1:comment-list'), self.course.uuid)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_create(self):
        body = {
            'course_uuid': self.course.uuid,
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_comment_path = ('course_discovery.apps.api.v1.views.comments.'
                               'SalesforceUtil.create_comment_for_course_case')

        with mock.patch(salesforce_path):
            with mock.patch(create_comment_path, return_value={
                'user': {
                    'username': self.user.username,
                    'email': self.user.email,
                    'first_name': self.user.first_name,
                    'last_name': self.user.last_name,
                },
                'comment': 'Comment body',
                'created': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }) as mock_create_comment:
                url = reverse('api:v1:comment-list')
                response = self.client.post(url, body, format='json')
                mock_create_comment.assert_called_with(
                    self.course,
                    self.request.user,
                    body.get('comment'),
                    course_run_key=body.get('course_run_key'),
                )
                self.assertEqual(response.status_code, 201)

    def test_create_400s_without_data(self):
        body = {}

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'

        with mock.patch(salesforce_path):
            url = reverse('api:v1:comment-list')
            response = self.client.post(url, body, format='json')
            self.assertEqual(response.status_code, 400)

    def test_create_403s_without_permissions(self):
        body = {
            'course_uuid': self.course.uuid,
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        is_editable_path = 'course_discovery.apps.api.v1.views.comments.CourseEditor.is_course_editable'

        with mock.patch(salesforce_path):
            with mock.patch(is_editable_path, return_value=False):
                url = reverse('api:v1:comment-list')
                response = self.client.post(url, body, format='json')
                self.assertEqual(response.status_code, 403)

    def test_create_404s_without_finding_course(self):
        body = {
            'course_uuid': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',  # Needs to resemble a uuid to pass validation
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'

        with mock.patch(salesforce_path):
            url = reverse('api:v1:comment-list')
            response = self.client.post(url, body, format='json')
            self.assertEqual(response.status_code, 404)

    def test_create_404s_without_a_config(self):
        body = {
            'course_uuid': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',  # Needs to resemble a uuid to pass validation
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'

        with mock.patch(salesforce_path):
            url = reverse('api:v1:comment-list')
            response = self.client.post(url, body, format='json')
            self.assertEqual(response.status_code, 404)

    def test_create_500s_without_a_successful_case_create(self):
        body = {
            'course_uuid': self.course.uuid,
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'
        create_comment_path = ('course_discovery.apps.api.v1.views.comments.'
                               'SalesforceUtil.create_comment_for_course_case')

        with mock.patch(salesforce_path):
            with mock.patch(create_comment_path, side_effect=SalesforceMissingCaseException('Error')):
                url = reverse('api:v1:comment-list')
                response = self.client.post(url, body, format='json')
                self.assertEqual(response.status_code, 500)

    def test_list_404s_without_a_config(self):
        self.salesforce_config.delete()
        body = {
            'course_uuid': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',  # Needs to resemble a uuid to pass validation
            'comment': 'Test comment',
            'course_run_key': 'test-key',
        }

        salesforce_path = 'course_discovery.apps.course_metadata.salesforce.Salesforce'

        with mock.patch(salesforce_path):
            url = reverse('api:v1:comment-list')
            response = self.client.post(url, body, format='json')
            self.assertEqual(response.status_code, 404)
