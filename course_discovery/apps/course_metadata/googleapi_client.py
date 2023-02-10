import logging
import re

from django.conf import settings
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from course_discovery.apps.course_metadata.constants import GOOGLE_CLIENT_API_SCOPE

logger = logging.getLogger(__name__)


class GoogleAPIClient:
    """
    API Client for Google API to communicate with drive files
    """

    def __init__(self):
        try:
            credentials = Credentials.from_service_account_info(
                settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS, scopes=GOOGLE_CLIENT_API_SCOPE
            )
            credentials = credentials.with_subject(settings.LOADER_INGESTION_CONTACT_EMAIL)
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info('[Connection Successful]: Successful connection with google service account')
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(f'[Connection Failed]: Failed to connect with google service account error_message: {ex}')

    def get_file_metadata(self, url):
        try:
            file_id = self.get_file_id_from_url(url)
            file = self.service.files().get(fileId=file_id).execute()  # pylint: disable=no-member
            logger.info(f'[File Found]: Found google file {file_id} on requesting {url}')
            return file
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(f'[File Not Found]: No file found for id: {file_id} error_message: {ex}')
        return None

    @staticmethod
    def get_file_id_from_url(url):
        match = re.search(r'id=(\w+)', url) or re.search(r'/(?:file/d/|uc\?id=)([-\w]{25,})(?:[&/]|$)', url)
        return match.group(1) if match else None

    def download_file_by_url(self, url):
        content = None
        try:
            file_id = self.get_file_id_from_url(url)
            request = self.service.files().get_media(fileId=file_id)  # pylint: disable=no-member
            content = request.execute()
            logger.info(f'[File Downloaded]: Downloading google file {file_id}')
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(f'[File Not Downloaded]: No file found for id: {file_id} error_message: {ex}')
        return content
