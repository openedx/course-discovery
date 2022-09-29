from unittest import mock

from django.test import TestCase

from course_discovery.apps.course_metadata.gspread_client import GspreadClient


class GspreadClientTests(TestCase):
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.gspread.service_account_from_dict')
    def test_connection_with_google(self, _mock_gspread_connection, mock_logger):
        GspreadClient()
        mock_logger.info.assert_called_with(
            '[Connection Successful]: Successful connection with google service account'
        )

    @mock.patch('course_discovery.apps.course_metadata.gspread_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.gspread.service_account_from_dict')
    def test_get_spread_sheet_by_key(self, _mock_gspread_connection, mock_logger):
        client = GspreadClient()
        client.get_spread_sheet_by_key('abc123Id')
        mock_logger.info.assert_called_with('[Spread Sheet Found]: Opening google sheet')

    @mock.patch('course_discovery.apps.course_metadata.gspread_client.logger')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.gspread.service_account_from_dict')
    def test_get_worksheet_data_by_tab_id(self, _mock_gspread_connection, mock_logger):
        client = GspreadClient()
        spread_sheet = mock.Mock()
        spread_sheet.worksheets.return_value = []
        client.get_worksheet_data_by_tab_id(spread_sheet, '123456')
        mock_logger.error.assert_called_with('[Worksheet Not Found]: No worksheet found with id: 123456')
