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
                "altName": "Alternative CSV Course",
                "abbreviation": "TC",
                "altAbbreviation": "UCT",
                "blurb": "A short description for CSV course",
                "language": "Español",
                "subjectMatter": "Marketing",
                "altSubjectMatter": "Design and Marketing",
                "altSubjectMatter1": "Marketing, Sales, and Techniques",
                "universityAbbreviation": "edX",
                "altUniversityAbbreviation": "altEdx",
                "cardUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS9pbWFnZS5qcGc=",
                "edxRedirectUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS8=",
                "edxPlpUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS8=",
                "durationWeeks": 10,
                "effort": "7–10 hours per week",
                'introduction': 'Very short description\n',
                'isThisCourseForYou': 'This is supposed to be a long description',
                'whatWillSetYouApart': "New ways to learn",
                "videoURL": "",
                "lcfURL": "www.example.com/lead-capture?id=123",
                "variant": {
                    "id": "test_id",
                    "endDate": "2022-05-06",
                    "finalPrice": "1998",
                    "startDate": "2022-03-06",
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
                "certificate": {
                    "headline": "About the certificate",
                    "blurb": "how this makes you special"
                },
                "stats": {
                    "stat1": "90%",
                    "stat1Blurb": "<p>A vast number of special beings take this course</p>",
                    "stat2": "100 million",
                    "stat2Blurb": "<p>VC fund</p>"
                }
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
    def test_successful_file_data_population_with_input_csv(self):
        """
        Verify the successful population has data from both input CSV and API response if input csv is provided.
        """
        self.mock_product_api_call()

        with NamedTemporaryFile() as input_csv:
            input_csv = self._write_csv(input_csv, [mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                output_csv = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
                call_command(
                    'populate_executive_education_data_csv',
                    '--input_csv', input_csv.name,
                    '--output_csv', output_csv.name,
                    '--auth_token', self.AUTH_TOKEN
                )
                output_csv.seek(0)
                reader = csv.DictReader(open(output_csv.name, 'r'))  # lint-amnesty, pylint: disable=consider-using-with
                data_row = next(reader)

                # Asserting certain data items to verify that both CSV and API
                # responses are present in the final CSV
                assert data_row['Organization'] == 'altEdx'
                assert data_row['External Identifier'] == '12345678'
                assert data_row['Start Time'] == '00:00:00'
                assert data_row['Short Description'] == 'A short description for CSV course'
                assert data_row['Long Description'] == 'Very short description\n' \
                                                       'This is supposed to be a long description'
                assert data_row['End Time'] == '23:59:59'
                assert data_row['Course Enrollment Track'] == 'Executive Education(2U)'
                assert data_row['Course Run Enrollment Track'] == 'Unpaid Executive Education'
                assert data_row['Length'] == '10'
                assert data_row['Number'] == 'TC'
                assert data_row['Redirect Url'] == 'https://example.com/'
                assert data_row['Organic Url'] == 'https://example.com/'
                assert data_row['Image'] == 'https://example.com/image.jpg'
                assert data_row['Course Level'] == 'Introductory'
                assert data_row['Course Pacing'] == 'Instructor-Paced'
                assert data_row['Content Language'] == 'Spanish - Spain (Modern)'
                assert data_row['Transcript Language'] == 'Spanish - Spain (Modern)'
                assert data_row['Primary Subject'] == 'Design and Marketing'
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

    @responses.activate
    def test_successful_file_data_population_without_input_csv(self):
        """
        Verify the successful population has data from API response only if optional input csv is not provided.
        """
        self.mock_product_api_call()

        with LogCapture(LOGGER_PATH) as log_capture:
            output_csv = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
            call_command(
                'populate_executive_education_data_csv',
                '--output_csv', output_csv.name,
                '--auth_token', self.AUTH_TOKEN
            )
            output_csv.seek(0)
            reader = csv.DictReader(open(output_csv.name, 'r'))  # lint-amnesty, pylint: disable=consider-using-with
            data_row = next(reader)

            self._assert_api_response(data_row)

            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    'Data population and transformation completed for CSV row title CSV Course'
                ),
            )

    @responses.activate
    def test_successful_file_data_population_input_csv_no_product_info(self):
        """
        Verify the successful population has data from API response only if optional input csv does not have
        the details of a particular product.
        """
        self.mock_product_api_call()
        mismatched_product = {
            **mock_data.VALID_COURSE_AND_COURSE_RUN_CSV_DICT,
            'title': 'Not present in CSV'
        }
        with NamedTemporaryFile() as input_csv:
            input_csv = self._write_csv(input_csv, [mismatched_product])

            with LogCapture(LOGGER_PATH) as log_capture:
                output_csv = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
                call_command(
                    'populate_executive_education_data_csv',
                    '--input_csv', input_csv.name,
                    '--output_csv', output_csv.name,
                    '--auth_token', self.AUTH_TOKEN
                )

                output_csv.seek(0)
                reader = csv.DictReader(open(output_csv.name, 'r'))  # lint-amnesty, pylint: disable=consider-using-with
                data_row = next(reader)

                self._assert_api_response(data_row)

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Data population and transformation completed for CSV row title CSV Course'
                    ),
                    (
                        LOGGER_PATH,
                        'WARNING',
                        '[MISSING PRODUCT IN CSV] Unable to find product details for product CSV Course in CSV'
                    ),
                )

    def test_invalid_csv_path(self):
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaisesMessage(
                CommandError, 'Error opening csv file at path /tmp/invalid_csv.csv'
        ):
            output_csv = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
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
            csv_file = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
            call_command(
                'populate_executive_education_data_csv',
                '--input_csv', csv_file.name,
                '--output_csv', csv_file.name,
                '--auth_token', self.AUTH_TOKEN
            )

    def _assert_api_response(self, data_row):
        """
        Assert the default API response in output CSV dict.
        """
        assert data_row['Organization'] == 'altEdx'
        assert data_row['2U Organization Code'] == 'edX'
        assert data_row['Edx Organization Code'] == 'altEdx'
        assert data_row['Number'] == 'TC'
        assert data_row['Alternate Number'] == 'UCT'
        assert data_row['Title'] == 'Alternative CSV Course'
        assert data_row['2U Title'] == 'CSV Course'
        assert data_row['Edx Title'] == 'Alternative CSV Course'
        assert data_row['2U Primary Subject'] == 'Marketing'
        assert data_row['Primary Subject'] == 'Design and Marketing'
        assert data_row['Subject Subcategory'] == 'Marketing, Sales, and Techniques'
        assert data_row['External Identifier'] == '12345678'
        assert data_row['Start Time'] == '00:00:00'
        assert data_row['Start Date'] == '2022-03-06'
        assert data_row['End Time'] == '23:59:59'
        assert data_row['End Date'] == '2022-05-06'
        assert data_row['Verified Price'] == '1998'
        assert data_row['Short Description'] == 'A short description for CSV course'
        assert data_row['Long Description'] == 'Very short description\n' \
                                               'This is supposed to be a long description'
        assert data_row['Course Enrollment Track'] == 'Executive Education(2U)'
        assert data_row['Course Run Enrollment Track'] == 'Unpaid Executive Education'
        assert data_row['Lead Capture Form Url'] == "www.example.com/lead-capture?id=123"
        assert data_row['Certificate Header'] == "About the certificate"
        assert data_row['Certificate Text'] == 'how this makes you special'
        assert data_row['Stat1'] == '90%'
        assert data_row['Stat1 Text'] == '<p>A vast number of special beings take this course</p>'
        assert data_row['Stat2'] == '100 million'
        assert data_row['Stat2 Text'] == '<p>VC fund</p>'
        assert data_row['Length'] == '10'
        assert data_row['Redirect Url'] == 'https://example.com/'
        assert data_row['Organic Url'] == 'https://example.com/'
        assert data_row['Image'] == 'https://example.com/image.jpg'
        assert data_row['Course Level'] == 'Introductory'
        assert data_row['Course Pacing'] == 'Instructor-Paced'
        assert data_row['Content Language'] == 'Spanish - Spain (Modern)'
        assert data_row['Transcript Language'] == 'Spanish - Spain (Modern)'

        assert data_row['Frequently Asked Questions'] == '<div><p><b>FAQ 1</b></p>This should answer it</div>'
        assert data_row['Syllabus'] == '<div><p>Test Curriculum</p><p><b>Module 0: </b>Welcome to your course' \
                                       '</p><p><b>Module 1: </b>Welcome to Module 1</p></div>'
        assert data_row['Learner Testimonials'] == '<div><p><i>" This is a good course"</i></p><p>-Lorem ' \
                                                   'Ipsum (Gibberish)</p></div>'
        assert str(date.today().year) in data_row['Publish Date']
