"""
Unit tests for the ingest_getsmarter_data management command.
"""
from unittest.mock import patch

import mock
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.constants import MOCK_PRODUCTS_DATA
from course_discovery.apps.course_metadata.tests.factories import SourceFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.ingest_getsmarter_data'


class IngestGetSmarterDataCommandTests(TestCase):
    """
    Tests for the ingest_getsmarter_data management command.
    """
    def setUp(self):
        super().setUp()
        self.source = SourceFactory(name='test source')
        self.products_data = {
            'products': MOCK_PRODUCTS_DATA
        }

    @mock.patch('course_discovery.apps.course_metadata.utils.GetSmarterEnterpriseApiClient')
    def test_executive_education_ingestion_command(self, mock_get_smarter_client):
        """
        Verify the command is called with correct arguments.
        """
        mock_get_smarter_client.return_value.request.return_value.json.return_value = self.products_data
        with patch('django.core.management.call_command') as mock_call_command, patch(LOGGER_PATH + '.logger.info') as mock_logger_info:  # pylint: disable=line-too-long
            call_command(
                'ingest_getsmarter_data',
                '--product_source', self.source.slug,
            )
            mock_logger_info.assert_has_calls([
                mock.call(
                    'Populating executive education data CSV file at path: %s', mock.ANY),
                mock.call(
                    'Ingesting executive education data from CSV file at path: %s', mock.ANY)
            ])
            mock_call_command.assert_any_call(
                'populate_executive_education_data_csv',
                use_getsmarter_api_client=True,
                output_csv=mock.ANY,
                product_source=self.source.slug,
            )
            mock_call_command.assert_any_call(
                'import_course_metadata',
                csv_path=mock.ANY,
                product_type='EXECUTIVE_EDUCATION',
                product_source=self.source.slug
            )

    def test_executive_education_ingestion_command__with_missing_product_source(self):
        """
        Verify the command raises CommandError if product_source is not passed.
        """
        with patch(LOGGER_PATH + '.logger.info') as mock_logger_info:
            with self.assertRaises(CommandError) as ex:
                call_command(
                    'ingest_getsmarter_data',
                )
            mock_logger_info.assert_not_called()
            self.assertEqual(
                "Error: the following arguments are required: --product_source",
                str(ex.exception)
            )
