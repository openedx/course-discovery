import logging
from urllib.parse import urljoin

import responses
from django.conf import settings
from django.test import TestCase

from course_discovery.apps.core.api_client import lms
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.mixins import LMSAPIClientMixin
from course_discovery.apps.core.tests.utils import MockLoggingHandler


class TestLMSAPIClient(LMSAPIClientMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logger = logging.getLogger(lms.__name__)
        cls.log_handler = MockLoggingHandler(level='DEBUG')
        logger.addHandler(cls.log_handler)
        cls.log_messages = cls.log_handler.messages

    def setUp(self):
        super().setUp()
        # Reset mock logger for each test.
        self.log_handler.reset()

        self.mock_access_token()

        self.user = UserFactory.create()
        self.partner = PartnerFactory.create(lms_url='http://127.0.0.1:8000')
        self.lms = lms.LMSAPIClient(self.partner)
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
        self.block_id = 'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc'
        resource = settings.LMS_API_URLS['blocks']
        self.block_resource_url = urljoin(self.partner.lms_url, resource + self.block_id)
        self.course_resource_url = urljoin(self.partner.lms_url, resource)
        self.block_metadata_base_url = urljoin(self.partner.lms_url, settings.LMS_API_URLS['block_metadata'])

    @responses.activate
    def test_get_api_access_request(self):
        """
        Verify that `get_api_access_request` returns correct value.
        """
        self.mock_api_access_request(
            self.partner.lms_url, self.user, api_access_request_overrides=self.response
        )
        assert self.lms.get_api_access_request(self.user) == self.response

    @responses.activate
    def test_get_api_access_request_with_404_error(self):
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API endpoint is not available.
        """
        self.mock_api_access_request(self.partner.lms_url, self.user, status=404)
        assert self.lms.get_api_access_request(self.user) is None
        assert 'HTTPError' in self.log_messages['error'][0]

    @responses.activate
    def test_get_api_access_request_with_empty_response(self):
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API endpoint is not available.
        """
        self.mock_api_access_request_with_invalid_data(
            self.partner.lms_url, self.user
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'KeyError' in self.log_messages['error'][0]

    @responses.activate
    def test_get_api_access_request_with_invalid_response(self):
        """
        Verify that `get_api_access_request` returns None when api_access_request
        returns an invalid response.
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
        assert 'KeyError' in self.log_messages['error'][0]

    @responses.activate
    def test_get_api_access_request_with_no_results(self):
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API returns no results.
        """
        self.mock_api_access_request_with_configurable_results(
            self.partner.lms_url, self.user, results=[]
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'No results for ApiAccessRequest for user [%s].' % self.user.username in self.log_messages['info']

    @responses.activate
    def test_get_api_access_request_cache_for_user_with_no_results(self):
        """
        Verify that `get_api_access_request` returns None when api_access_request
        API returns no results and returns the cached result on another call with
        the same user.
        """
        self.mock_api_access_request_with_configurable_results(
            self.partner.lms_url, self.user, results=[]
        )
        assert self.lms.get_api_access_request(self.user) is None
        assert 'No results for ApiAccessRequest for user [%s].' % self.user.username in self.log_messages['info']

        assert self.lms.get_api_access_request(self.user) is None
        assert len(responses.calls) == 1

    @responses.activate
    def test_get_api_access_request_cache_hit(self):
        """
        Verify that `get_api_access_request` returns the correct value and then
        returns the cached results on another call with the same user.
        """
        self.mock_api_access_request(
            self.partner.lms_url, self.user, api_access_request_overrides=self.response
        )
        assert self.lms.get_api_access_request(self.user) == self.response
        assert self.lms.get_api_access_request(self.user) == self.response
        assert len(responses.calls) == 1

    @responses.activate
    def test_get_api_access_request_with_multiple_records(self):
        """
        Verify that `get_api_access_request` logs a warning message and returns the first result
        if endpoint returns multiple api-access-requests for a user.
        """
        results = [
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
        ]

        self.mock_api_access_request_with_configurable_results(
            self.partner.lms_url, self.user, results=results
        )

        assert self.lms.get_api_access_request(self.user)['company_name'] == 'Test Company'
        assert 'Multiple ApiAccessRequest models returned from LMS API for user [%s].' % self.user.username in \
               self.log_messages['warning']

    @responses.activate
    def test_get_course_blocks_data(self):
        """
        Verify that `get_course_blocks_data` returns correct value.
        """
        data = self.mock_blocks_data_request(self.course_resource_url)
        assert self.lms.get_course_blocks_data('dummy-course-id') == data['blocks']

    @responses.activate
    def test_get_blocks_data(self):
        """
        Verify that `get_blocks_data` returns correct value.
        """
        data = self.mock_blocks_data_request(self.block_resource_url)
        assert self.lms.get_blocks_data(self.block_id) == data['blocks']

    @responses.activate
    def test_get_block_metadata(self):
        """
        Verify that `get_blocks_metadata` returns correct value.
        """
        data = self.mock_block_metadata_request(self.block_metadata_base_url)
        assert self.lms.get_blocks_metadata(self.block_id) == data[self.block_id]

    @responses.activate
    def test_get_blocks_data_with_no_results(self):
        """
        Verify that `get_blocks_data` returns None when
        API returns no results.
        """
        self.mock_blocks_data_request(self.block_resource_url, override_blocks={})
        assert not self.lms.get_blocks_data(self.block_id)
        assert 'No blocks found for [%s].' % self.block_id in self.log_messages['info']

    @responses.activate
    def test_get_blocks_data_cache_hit(self):
        """
        Verify that `get_blocks_data` returns the correct value and then
        returns the cached results on another call with the same block_id.
        """
        data = self.mock_blocks_data_request(self.block_resource_url)
        assert self.lms.get_blocks_data(self.block_id) == data['blocks']
        assert self.lms.get_blocks_data(self.block_id) == data['blocks']
        assert len(responses.calls) == 1
