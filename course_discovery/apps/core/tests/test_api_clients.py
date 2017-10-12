import logging

import mock
import responses
from django.test import TestCase

from course_discovery.apps.core.api_client import lms
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.mixins import LMSAPIClientMixin
from course_discovery.apps.core.tests.utils import MockLoggingHandler


class TestLMSAPIClient(LMSAPIClientMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLMSAPIClient, cls).setUpClass()
        logger = logging.getLogger(lms.__name__)
        cls.log_handler = MockLoggingHandler(level='DEBUG')
        logger.addHandler(cls.log_handler)
        cls.log_messages = cls.log_handler.messages

    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def setUp(self, mock_access_token):  # pylint: disable=unused-argument
        super(TestLMSAPIClient, self).setUp()

        # Reset mock logger for each test.
        self.log_handler.reset()

        self.user = UserFactory.create()
        self.partner = PartnerFactory.create()
        self.lms = lms.LMSAPIClient(self.partner.site)
        self.response = {
            'id': 1,
            'created': '2017-09-25T08:37:05.872566Z',
            'modified': '2017-09-25T08:37:47.412496Z',
            'user': 1,
            'status': 'approved',
            'website': 'https://example.com/',
            'reason': 'Example Reason',
            'company_name': 'Test Company',
            'company_address': 'Example Address',
            'site': 1,
            'contacted': True
        }

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_api_access_request(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_api_access_request` returns correct value.
        """
        self.mock_api_access_request(
            self.partner.lms_url, self.user, api_access_request_overrides=self.response
        )
        assert self.lms.get_api_access_request(self.user) == self.response

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_api_access_request_with_404_error(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API endpoint is not available.
        """
        self.mock_api_access_request(
            self.partner.lms_url, self.user, status=404
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'Failed to fetch API Access Request from LMS for user "%s".' % self.user.username in \
               self.log_messages['error']

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_api_access_request_with_empty_response(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API endpoint is not available.
        """
        self.mock_api_access_request_with_invalid_data(
            self.partner.lms_url, self.user
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'APIAccessRequest model not found for user [%s].' % self.user.username in \
               self.log_messages['info']

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_api_access_request_with_invalid_response(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API endpoint is not available.
        """
        # API response without proper paginated structure.
        # Following is an invalid response.
        sample_invalid_response = {
            'id': 1,
            'created': '2017-09-25T08:37:05.872566Z',
            'modified': '2017-09-25T08:37:47.412496Z',
            'user': 5,
            'status': 'approved',
            'website': 'https://example.com/',
            'reason': 'Example Reason',
            'company_name': 'Example Inc',
            'company_address': 'Example Address',
            'site': 1,
            'contacted': True
        }

        self.mock_api_access_request_with_invalid_data(
            self.partner.lms_url, self.user, response_overrides=sample_invalid_response
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'APIAccessRequest model not found for user [%s].' % self.user.username in \
               self.log_messages['info']

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_api_access_request_with_multiple_records(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_api_access_request` logs a warning message and returns the first result
        if endpoint returns multiple api-access-requests for a user.
        """
        # API response without proper paginated structure.
        # Following is an invalid response.
        sample_response_with_multiple_users = {
            'count': 2,
            'num_pages': 1,
            'current_page': 1,
            'results':
                [
                    {
                        'id': 1,
                        'created': '2017-09-25T08:37:05.872566Z',
                        'modified': '2017-09-25T08:37:47.412496Z',
                        'user': 1,
                        'status': 'declined',
                        'website': 'https://example.com/',
                        'reason': 'Example Reason',
                        'company_name': 'Test Company',
                        'company_address': 'Example Address',
                        'site': 1,
                        'contacted': True
                    },
                    {
                        'id': 2,
                        'created': '2017-10-25T08:37:05.872566Z',
                        'modified': '2017-10-25T08:37:47.412496Z',
                        'user': 1,
                        'status': 'approved',
                        'website': 'https://example.com/',
                        'reason': 'Example Reason',
                        'company_name': 'Test Company',
                        'company_address': 'Example Address',
                        'site': 1,
                        'contacted': True
                    },
                ],
            'next': None,
            'start': 0,
            'previous': None
        }

        self.mock_api_access_request_with_invalid_data(
            self.partner.lms_url, self.user, response_overrides=sample_response_with_multiple_users
        )

        assert self.lms.get_api_access_request(self.user)['company_name'] == 'Test Company'
        assert 'Multiple APIAccessRequest models returned from LMS API for user [%s].' % self.user.username in \
               self.log_messages['warning']
