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

    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient.get_spread_sheet_by_key')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient.get_worksheet_data_by_tab_id')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.logger')
    def test_read_data(self, _mock_logger, mock_get_worksheet_data_by_tab_id, mock_get_spread_sheet_by_key):
        """
        Test read_data method of Gspread client with mock data
        """
        mock_spreadsheet = mock.Mock()
        mock_worksheet_data = [{'header1': 'value1', 'header2': 'value2'}]
        mock_get_spread_sheet_by_key.return_value = mock_spreadsheet
        mock_get_worksheet_data_by_tab_id.return_value = mock_worksheet_data

        client = GspreadClient()
        config = {'SHEET_ID': 'sheet_id', 'INPUT_TAB_ID': 'input_tab_id'}
        result = client.read_data(config)

        mock_get_spread_sheet_by_key.assert_called_once_with('sheet_id')
        mock_get_worksheet_data_by_tab_id.assert_called_once_with(mock_spreadsheet, 'input_tab_id')
        self.assertEqual(result, mock_worksheet_data)

    @mock.patch(
        "course_discovery.apps.course_metadata.gspread_client.ascii_uppercase",
        new=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    )
    def test_write_headers(self):
        """
        Test write_headers method of Gspread client
        """
        mock_sheet_tab = mock.Mock()
        headers = ['header1', 'header2']

        client = GspreadClient()
        client._write_headers(mock_sheet_tab, headers)  # pylint: disable=protected-access

        mock_sheet_tab.append_row.assert_called_once_with(headers)
        mock_sheet_tab.format.assert_called_once_with('A1:B1', {'textFormat': {'bold': True}})

    def test_write_rows(self):
        """
        Test write_rows method of Gspread client
        """
        mock_sheet_tab = mock.Mock()
        headers = ['header1', 'header2']
        csv_data = [{'header1': 'value1', 'header2': 'value2'}, {'header1': 'value3', 'header2': 'value4'}]

        client = GspreadClient()
        client._write_rows(mock_sheet_tab, headers, csv_data)  # pylint: disable=protected-access

        mock_sheet_tab.append_row.assert_any_call(['value1', 'value2'])
        mock_sheet_tab.append_row.assert_any_call(['value3', 'value4'])
        self.assertEqual(mock_sheet_tab.append_row.call_count, 2)

    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient._get_or_create_worksheet')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient._write_headers')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient._write_rows')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.GspreadClient.get_spread_sheet_by_key')
    @mock.patch('course_discovery.apps.course_metadata.gspread_client.logger')
    def test_write_data(
        self,
        _mock_logger,
        mock_get_spread_sheet_by_key,
        mock_write_rows,
        mock_write_headers,
        mock_get_or_create_worksheet,
    ):
        """
        Test write_data method of Gspread client with mock data
        """
        mock_spreadsheet = mock.Mock()
        mock_sheet_tab = mock.Mock()
        mock_get_spread_sheet_by_key.return_value = mock_spreadsheet
        mock_get_or_create_worksheet.return_value = mock_sheet_tab

        client = GspreadClient()
        config = {"SHEET_ID": "sheet_id", "OUTPUT_TAB_ID": "output_tab_id"}
        csv_headers = ["header1", "header2"]
        csv_data = [{"header1": "value1", "header2": "value2"}]

        client.write_data(config, csv_headers, csv_data, overwrite=True)

        mock_get_spread_sheet_by_key.assert_called_once_with("sheet_id")
        mock_get_or_create_worksheet.assert_called_once_with(
            mock_spreadsheet, "output_tab_id", len(csv_headers) + 1, len(csv_data) + 1
        )
        mock_sheet_tab.clear.assert_called_once()
        mock_write_headers.assert_called_once_with(mock_sheet_tab, csv_headers)
        mock_write_rows.assert_called_once_with(mock_sheet_tab, csv_headers, csv_data)
