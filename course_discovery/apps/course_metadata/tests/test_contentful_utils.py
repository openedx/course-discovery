"""
Unit tests for Contentful Utility Functions
"""
from unittest import mock

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.contentful_utils import (
    contentful_cache_key, fetch_and_transform_bootcamp_contentful_data, get_aggregated_data_from_contentful_data,
    get_data_from_contentful, rich_text_to_plain_text
)
from course_discovery.apps.course_metadata.tests.contentful_bootcamp_mock_data import (
    MockContentBootcampResponse, about_the_program_entry, bootcamp_transformed_data, mock_contentful_bootcamp_entry
)

LOGGER_NAME = 'course_discovery.apps.course_metadata.contentful_utils'


@pytest.mark.usefixtures('django_cache')
class TestContentfulUtils(TestCase):
    """
    Test get_data_from_contentful.
    """

    @mock.patch('course_discovery.apps.course_metadata.contentful_utils.Client')
    def test_get_data_from_contentful(self, mock_client):
        """
        Test get_data_from_contentful utility with mock data.
        """
        mock_client.return_value.entries.return_value = MockContentBootcampResponse
        contentful_data = get_data_from_contentful(settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE)
        assert len(contentful_data) == 2
        assert contentful_data[0] == mock_contentful_bootcamp_entry
        self.assertDictEqual(contentful_data[0].raw, mock_contentful_bootcamp_entry.raw)

    @mock.patch('course_discovery.apps.course_metadata.contentful_utils.Client')
    def test_get_cached_data_from_contentful(self, mock_client):
        """
        Test get_data_from_contentful utility with mock data.
        """
        self.maxDiff = None
        mock_client.return_value.entries.return_value = MockContentBootcampResponse
        cache_key = contentful_cache_key(settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE)
        assert cache.get(cache_key) is None
        _ = get_data_from_contentful(settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE)
        assert cache.get(cache_key) is not None

        with LogCapture(LOGGER_NAME) as log_capture:
            contentful_data = get_data_from_contentful(settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE)

            log_capture.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    f'Using cached Contentful entries data and skipping API call for '
                    f'{settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE}',
                )
            )
            assert len(contentful_data) == 2
            assert contentful_data[0].uuid == mock_contentful_bootcamp_entry.uuid

    def test_rich_text_to_plain_text(self):
        """
        Test rich_text_to_plain_text utility which transforms rich text to plain text.
        """
        plain_text = rich_text_to_plain_text(about_the_program_entry.content)
        expected_text = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit'
        assert plain_text == expected_text

    @mock.patch('course_discovery.apps.course_metadata.contentful_utils.get_data_from_contentful',
                return_value=[mock_contentful_bootcamp_entry])
    def test_transform_bootcamp_contentful_data(self, *args):
        """
        Test transform_bootcamp_contentful_data given a mocked entry from contentful.
        """
        transformed_data = fetch_and_transform_bootcamp_contentful_data()
        self.assertDictEqual(transformed_data, bootcamp_transformed_data)

    def test_get_aggregated_data_from_contentful_data(self):
        expected_data = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet, ' \
                        'consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem ' \
                        'ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur ' \
                        'adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit ' \
                        'amet, consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit ' \
                        'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, ' \
                        'consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem ' \
                        'ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur ' \
                        'adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum: dolor ' \
                        'sit amet, consectetur adipiscing elitLorem ipsum: dolor sit amet, consectetur adipiscing ' \
                        'elitLorem ipsum: dolor sit amet, consectetur adipiscing elitLorem ipsum: dolor sit amet, ' \
                        'consectetur adipiscing elit'

        assert get_aggregated_data_from_contentful_data({}, 'uuid_123') is None
        assert get_aggregated_data_from_contentful_data(bootcamp_transformed_data, 'no_uuid') is None
        assert get_aggregated_data_from_contentful_data(bootcamp_transformed_data, 'test-uuid') == expected_data
