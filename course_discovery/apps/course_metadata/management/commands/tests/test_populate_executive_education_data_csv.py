"""
Unit tests for populate_executive_education_data_csv management command.
"""
import csv
import json
from datetime import date
from tempfile import NamedTemporaryFile

import responses
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import CSVLoaderMixin

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.populate_executive_education_data_csv'


class TestPopulateExecutiveEducationDataCsv(CSVLoaderMixin, TestCase):
    """
    Test suite for populate_executive_education_data_csv management command.
    """
    AUTH_TOKEN = 'auth_token'
    SUCCESS_API_RESPONSE = {
        'products': [
            {
                "id": "12345678",
                "name": "CSV Course",
                "abbreviation": "TC",
                "language": "Español",
                "subjectMatter": "Marketing",
                "universityAbbreviation": "edX",
                "cardUrl": "https://example.com/image.jpg",
                "edxRedirectUrl": "https://example.com/",
                "durationWeeks": 10,
                "effort": "7–10 hours per week",
                'introduction': 'Very short description\n',
                'isThisCourseForYou': 'This is supposed to be a long description',
                "videoURL": "",
                "variant": {
                    "id": "test_id",
                    "endDate": "2022-05-06",
                },
                "curriculum": {
                    "heading": "Course curriculum",
                    "blurb": "Test Curriculum",
                    "modules": [
                        {
                            "module_number": 0,
                            "heading": "Module 0",
                            "description": "Welcome to your course"
                        },
                        {
                            "module_number": 1,
                            "heading": "Module 1",
                            "description": "Welcome to Module 1"
                        },
                    ]
                },
                "testimonials": [
                    {
                        "name": "Lorem Ipsum",
                        "title": "Gibberish",
                        "text": " This is a good course"
                    },
                ],
                "faqs": [
                    {
                        "id": "faq-1",
                        "headline": "FAQ 1",
                        "blurb": "This should answer it"
                    }
                ],
            },
        ]}

    def mock_product_api_call(self):
        """
        Mock product api with success response.
        """
        responses.add(
            responses.GET,
            settings.PRODUCT_API_URL + '/?detail=1',
            body=json.dumps(self.SUCCESS_API_RESPONSE),
            status=200,
        )

    @responses.activate
    def test_successful_file_data_population(self):
        """
        Verify the successful population has data from both input CSV and API response.
        """
        self.mock_product_api_call()

        with NamedTemporaryFile() as input_csv:
            input_csv = self._write_csv(input_csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                output_csv = NamedTemporaryFile()
                call_command(
                    'populate_executive_education_data_csv',
                    '--input_csv', input_csv.name,
                    '--output_csv', output_csv.name,
                    '--auth_token', self.AUTH_TOKEN
                )
                output_csv.seek(0)
                reader = csv.DictReader(open(output_csv.name, 'r'))
                data_row = next(reader)

                # Asserting certain data items to verify that both CSV and API
                # responses are present in the final CSV
                assert data_row['Organization'] == 'edX'
                assert data_row['External Identifier'] == '12345678'
                assert data_row['Start Time'] == '00:00:00'
                assert data_row['Short Description'] == 'CSV Course'
                assert data_row['Long Description'] == 'Very short description\n' \
                                                       'This is supposed to be a long description'
                assert data_row['End Time'] == '23:59:59'
                assert data_row['Course Enrollment Track'] == 'Executive Education'
                assert data_row['Course Run Enrollment Track'] == 'Executive Education'
                assert data_row['Length'] == '10'
                assert data_row['Number'] == 'TC'
                assert data_row['Course Level'] == 'Introductory'
                assert data_row['Course Pacing'] == 'Instructor-Paced'
                assert data_row['Content Language'] == 'Spanish - Spain (Modern)'
                assert data_row['Transcript Language'] == 'Spanish - Spain (Modern)'
                assert data_row['Primary Subject'] == 'Marketing'
                assert data_row['Frequently Asked Questions'] == '<div><p><b>FAQ 1</b></p>This should answer it</div>'
                assert data_row['Syllabus'] == '<div><p>Test Curriculum</p><p><b>Module 0: </b>Welcome to your course' \
                                               '</p><p><b>Module 1: </b>Welcome to Module 1</p></div>'
                assert data_row['Learner Testimonials'] == '<div><p><i>" This is a good course"</i></p><p>-Lorem ' \
                                                           'Ipsum (Gibberish)</p></div>'
                assert str(date.today().year) in data_row['Publish Date']

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Data population and transformation completed for CSV row title CSV Course'
                    ),
                )

    def test_invalid_csv_path(self):
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaisesMessage(
                CommandError, 'Error opening csv file at path /tmp/invalid_csv.csv'
        ):
            output_csv = NamedTemporaryFile()
            call_command(
                'populate_executive_education_data_csv',
                '--input_csv', '/tmp/invalid_csv.csv',
                '--output_csv', output_csv.name,
                '--auth_token', self.AUTH_TOKEN
            )

    @responses.activate
    def test_product_api_call_failure(self):
        """
        Test the command raises an error if the product API call fails for some reason.
        """
        responses.add(
            responses.GET,
            settings.PRODUCT_API_URL + '/?detail=1',
            status=400,
        )
        with self.assertRaisesMessage(
                CommandError, 'Unexpected error occurred while fetching products'
        ):
            csv_file = NamedTemporaryFile()
            call_command(
                'populate_executive_education_data_csv',
                '--input_csv', csv_file.name,
                '--output_csv', csv_file.name,
                '--auth_token', self.AUTH_TOKEN
            )
