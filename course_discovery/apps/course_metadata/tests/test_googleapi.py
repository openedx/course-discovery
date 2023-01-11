from unittest import mock

import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.googleapi_client import GoogleAPIClient


@ddt.ddt
class GoogleAPIClientTests(TestCase):

    Google_DRIVE_API_TEST_DATA = [
        ('https://docs.google.com/uc?id=abc123Id', 'abc123Id'),
        ('https://drive.google.com/file/d/1Xv36dVXFC-eU2Oks_EcRdbtgv47D-osP/view?usp=sharing', '1Xv36dVXFC-eU2Oks_EcRdbtgv47D-osP'),  # pylint: disable=line-too-long
    ]

    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials.with_subject')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.build')
    def test_connection_with_google(self, mock_googleapi_connection, mock_account_credentials, _mock_with_subject, mock_logger):  # pylint: disable=line-too-long
        GoogleAPIClient()
        assert mock_account_credentials.from_service_account_info.called is True
        assert mock_googleapi_connection.called is True
        mock_logger.info.assert_called_with(
            '[Connection Successful]: Successful connection with google service account'
        )

    @ddt.data(*Google_DRIVE_API_TEST_DATA)
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials.with_subject')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.build')
    @ddt.unpack
    def test_get_file_id_from_url(self, file_url, expected_file_id, mock_googleapi_connection, mock_account_credentials, _mock_with_subject):  # pylint: disable=line-too-long
        client = GoogleAPIClient()
        assert mock_account_credentials.from_service_account_info.called is True
        assert mock_googleapi_connection.called is True
        file_id = client.get_file_id_from_url(file_url)
        assert file_id == expected_file_id

    @ddt.data(*Google_DRIVE_API_TEST_DATA)
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials.with_subject')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.build')
    @ddt.unpack
    def test_get_file_metadata(self, file_url, expected_file_id, mock_googleapi_connection, mock_account_credentials, _mock_with_subject, mock_logger):  # pylint: disable=line-too-long
        client = GoogleAPIClient()
        assert mock_account_credentials.from_service_account_info.called is True
        assert mock_googleapi_connection.called is True
        client.get_file_metadata(file_url)
        mock_logger.info.assert_called_with(
            f'[File Found]: Found google file {expected_file_id} on requesting {file_url}'
        )

    @ddt.data(*Google_DRIVE_API_TEST_DATA)
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials.with_subject')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.Credentials')
    @mock.patch('course_discovery.apps.course_metadata.googleapi_client.build')
    @ddt.unpack
    def test_download_file_by_url(self, file_url, expected_file_id, _mock_googleapi_connection, _mock_account_credentials, _mock_with_subject, mock_logger):  # pylint: disable=line-too-long
        client = GoogleAPIClient()
        client.download_file_by_url(file_url)
        mock_logger.info.assert_called_with(f'[File Downloaded]: Downloading google file {expected_file_id}')
