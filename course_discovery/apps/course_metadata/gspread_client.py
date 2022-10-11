import logging

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
