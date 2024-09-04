import logging
from string import ascii_uppercase

import gspread
from django.conf import settings

logger = logging.getLogger(__name__)


class GspreadClient:
    """
    API Client for GSpread to communicate with google spread sheets and drive images
    """

    def __init__(self):
        try:
            self.client = gspread.service_account_from_dict(settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS)
            logger.info('[Connection Successful]: Successful connection with google service account')
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(f'[Connection Failed]: Failed to connect with google service account error_message: {ex}')

    def get_spread_sheet_by_key(self, key):
        try:
            spread_sheet = self.client.open_by_key(key)
            logger.info('[Spread Sheet Found]: Opening google sheet')
            return spread_sheet
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(f'[Spread Sheet Not Found]: No spreadsheet found for key: {key} error_message: {ex}')
        return None

    def read_data(self, config):
        # TODO: add unit tests
        try:
            spread_sheet = self.get_spread_sheet_by_key(config['SHEET_ID'])
            input_tab = self.get_worksheet_data_by_tab_id(spread_sheet, config['INPUT_TAB_ID'])
            return input_tab
        except Exception:  # pylint: disable=broad-except
            logger.exception('[Spread Sheet Read Error]: Exception occurred while reading sheet data')
        return None

    def _get_or_create_worksheet(self, spread_sheet, tab_id, cols, rows):
        """
        Get or create a worksheet with the given tab_id in the given spread_sheet

        Args:
            spread_sheet: The spread sheet object
            tab_id: The tab id of the worksheet
            cols: The number of columns in the worksheet
            rows: The number of rows in the worksheet
        """
        try:
            return spread_sheet.worksheet(tab_id)
        except gspread.exceptions.WorksheetNotFound:
            return spread_sheet.add_worksheet(
                title=tab_id,
                rows=rows,
                cols=cols,
            )

    def _write_headers(self, sheet_tab, headers):
        """
        Write headers to the first row of the worksheet

        Args:
            sheet_tab: The worksheet object
            headers: The headers of the worksheet
        """
        sheet_tab.append_row(headers)
        end_column = ascii_uppercase[len(headers) - 1]
        cell_range = f"A1:{end_column}1"
        sheet_tab.format(cell_range, {'textFormat': {'bold': True}})

    def _write_rows(self, sheet_tab, headers, csv_data):
        """
        Write rows to the worksheet after headers

        Args:
            sheet_tab: The worksheet object
            headers: The headers of the worksheet
            csv_data: The data to be written in the worksheet, as a list of dictionaries, where
            each dictionary represents a row
        """
        rows = [
            [
                row.get(header).replace('\"', '\"\"') if isinstance(row.get(header), str) else row.get(header)
                for header in headers
            ]
            for row in csv_data
        ]
        try:
            sheet_tab.append_rows(rows)
        except gspread.exceptions.APIError as e:
            logger.exception(f"[Spread Sheet Write Error]: APIError occurred while writing rows: {e}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[Spread Sheet Write Error]: Exception occurred while writing rows: {e}")

    def write_data(self, config, csv_headers, csv_data, overwrite):
        """
        Write data to the google spread sheet

        Args:
            config: The configuration for the google spread sheet
            csv_headers: The headers of the data to be written in the worksheet
            csv_data: The data to be written in the worksheet, as a list of dictionaries, where
            each dictionary represents a row
            overwrite: Whether to overwrite the existing data in the worksheet
        """
        try:
            spread_sheet = self.get_spread_sheet_by_key(config["SHEET_ID"])
            sheet_tab = self._get_or_create_worksheet(
                spread_sheet, config["OUTPUT_TAB_ID"], len(csv_headers) + 1, len(csv_data) + 1
            )

            if overwrite:
                sheet_tab.clear()

            if csv_headers:
                self._write_headers(sheet_tab, csv_headers)

            self._write_rows(sheet_tab, csv_headers, csv_data)

            logger.info(
                f"""
                    [Spread Sheet Write Success]: Successfully written data to
                    sheet {config["SHEET_ID"]} tab {config["OUTPUT_TAB_ID"]}
                """
            )
        except gspread.exceptions.GSpreadException as e:
            logger.exception(f"[Spread Sheet Write Error]: GSpreadException occurred while writing sheet data: {e}")
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"[Spread Sheet Write Error]: Exception occurred while writing sheet data: {e}")

    @staticmethod
    def get_worksheet_data_by_tab_id(spread_sheet, tab_id):
        try:
            tab_id = int(tab_id)
            worksheet_title = [ws.title for ws in spread_sheet.worksheets() if ws.id == tab_id]
            if not worksheet_title:
                logger.error(f'[Worksheet Not Found]: No worksheet found with id: {tab_id}')
                return None
            ws = spread_sheet.worksheet(worksheet_title[0])
            logger.info('[Worksheet Found]: Getting data for worksheet tab')
            return ws.get_all_records()
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(
                f'[Worksheet Not Found]: unable to get data for worksheet tab with id: {tab_id} error_message: {ex}'
            )
        return None
