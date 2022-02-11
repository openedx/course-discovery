"""
Management command to transform and populate a partially filled data CSV using data from Product API.
```
./manage.py populate_executive_education_data_csv --auth_token=<api_token> --input_csv=<path> --output_csv=<path>

Note: This management command is meant to be run on local or a limited space and not on any server. Plus, it
will be removed in the future once it serves its purpose.
```
"""
import csv
import json
import logging
from datetime import date

import requests
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.data_loaders import utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate and transform data CSV'

    # The list to define order of the header keys in csv.
    OUTPUT_CSV_HEADERS = [
        'organization', 'title', 'number', 'course_enrollment_track', 'image', 'short_description',
        'long_description', 'what_will_you_learn', 'course_level', 'primary_subject', 'verified_price', 'collaborators',
        'syllabus', 'prerequisites', 'learner_testimonials', 'frequently_asked_questions', 'additional_information',
        'about_video_link', 'secondary_subject', 'tertiary_subject',
        'course_embargo_(ofac)_restriction_text_added_to_the_faq_section', 'publish_date',
        'start_date', 'start_time', 'end_date', 'end_time', 'course_run_enrollment_track', 'course_pacing', 'staff',
        'minimum_effort', 'maximum_effort', 'length', 'content_language', 'transcript_language',
        'expected_program_type', 'expected_program_name', 'upgrade_deadline_override_date',
        'upgrade_deadline_override_time', 'redirect_url', 'external_identifier'
    ]

    # Mapping English and Spanish languages to IETF equivalent variants
    LANGUAGE_MAP = {
        'English': 'English - United States',
        'Español': 'Spanish - Spain (Modern)',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth_token',
            dest='auth_token',
            type=str,
            required=True,
            help='Bearer token for making API calls to Product API'
        )
        parser.add_argument(
            '--input_csv',
            dest='input_csv',
            type=str,
            required=True,
            help='Path to partially filled input CSV'
        )
        parser.add_argument(
            '--output_csv',
            dest='output_csv',
            type=str,
            required=True,
            help='Path of the output CSV'
        )

    def handle(self, *args, **options):
        input_csv = options.get('input_csv')
        output_csv = options.get('output_csv')
        auth_token = options.get('auth_token')

        try:
            input_reader = csv.DictReader(open(input_csv, 'r'))
        except FileNotFoundError:
            raise CommandError(  # pylint: disable=raise-missing-from
                "Error opening csv file at path {}".format(input_csv)
            )

        products = self.get_product_details(auth_token)
        if not products:
            raise CommandError("Unexpected error occurred while fetching products")

        with open(output_csv, 'w', newline='') as output_writer:

            output_writer = self.write_csv_header(output_writer)

            for row in input_reader:
                row = self.transform_dict_keys(row)
                product = [product_item for product_item in products if product_item['name'] == row['title']]
                if not product or len(product) != 1:
                    logger.error("[MISSING PRODUCT IN API] Unable to find product details for CSV row title {}".format(
                        row['title']
                    ))
                    continue
                output_dict = self.get_transformed_data(row, product[0])
                output_writer = self.write_csv_row(output_writer, output_dict)
                logger.info("Data population and transformation completed for CSV row title {}".format(
                    row['title']
                ))

    def transform_dict_keys(self, data):
        """
        Given a data dictionary, return a new dict that has its keys transformed to
        snake case. For example, Enrollment Track becomes enrollment_track.

        Each key is stripped of whitespaces around the edges, converted to lower case,
        and has internal spaces converted to _. This convention removes the dependency on CSV
        headers format(Enrollment Track vs Enrollment track) and makes code flexible to ignore
        any case sensitivity, among other things.
        """
        transformed_dict = {}
        for key, value in data.items():
            updated_key = key.strip().lower().replace(' ', '_')
            transformed_dict[updated_key] = value
        return transformed_dict

    def get_product_details(self, auth_token):
        """
        Method to get all products from provided product API.
        """
        url = settings.PRODUCT_API_URL
        headers = {
            "Authorization": f"Bearer {auth_token}"
        }
        params = {
            "detail": 1
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            response = response.json()

            if 'products' in response:
                products = response['products']
                return products
            else:
                print(f"No products found in API response: {response}")

        except requests.exceptions.HTTPError as e:
            print(f"API Call failed with message {e}")

        return []

    def mock_product_details(self):
        """
        Dev Helper method to read response from file to ease development process.
        """
        with open('course_discovery/apps/course_metadata/management/commands/data.json', 'r') as f:
            data = json.load(f)
            products = data['products']
            return products

    def write_csv_header(self, output_csv):
        """
        Write the header of output CSV in the file.
        """
        header = ''
        for key in self.OUTPUT_CSV_HEADERS:
            title_case_key = key.replace('_', ' ').title()
            header = '{}"{}",'.format(header, title_case_key)
        header = f"{header[:-1]}\n"

        output_csv.write(header)
        return output_csv

    def write_csv_row(self, output_csv, data_dict):
        """
        Helper method to write a given data dict as row in output CSV.
        """
        lines = ''
        for key in self.OUTPUT_CSV_HEADERS:
            if isinstance(data_dict[key], str):
                output = data_dict[key].replace('\"', '\"\"')  # double quote escape to preserve " in values
            else:
                output = data_dict[key]
            lines = '{}"{}",'.format(lines, output)
        lines = f"{lines[:-1]}\n"
        output_csv.write(lines)
        return output_csv

    def get_transformed_data(self, partially_filled_csv_dict, product_dict):
        """
        Returns the final representation of the data row using partially filled dict
        and the product dict.
        """
        # TODO: To use util method once the changes are merged
        minimum_effort, maximum_effort = 7, 10

        language = self.LANGUAGE_MAP.get(product_dict['language'], 'English - United States')

        default_values = {  # the values that will be part of every output row in any case
            'course_enrollment_track': 'Executive Education',
            'course_run_enrollment_track': 'Executive Education',
            'start_time': '00:00:00',
            'end_time': '23:59:59',
            'publish_date': date.today().isoformat(),
            'course_level': 'Introductory',
            'course_pacing': 'Instructor-Paced',
            'content_language': language,
            'transcript_language': language,
            'staff': '',
            'expected_program_type': '',
            'expected_program_name': '',
            'upgrade_deadline_override_date': '',
            'upgrade_deadline_override_time': '',
            'course_embargo_(ofac)_restriction_text_added_to_the_faq_section': '',
        }
        # TODO: To decode card and video URLs with util once the changes are merged
        card_url = product_dict['cardUrl'] if product_dict['cardUrl'] is not None else ''
        video_url = product_dict['videoURL'] if product_dict['videoURL'] is not None else ''
        redirect_url = product_dict['edxRedirectUrl'] if product_dict['edxRedirectUrl'] is not None else ''

        return {
            **default_values,
            'organization': product_dict['universityAbbreviation'],
            'number': product_dict['abbreviation'],
            'image': card_url,
            'primary_subject': product_dict['subjectMatter'],
            'syllabus': utils.format_curriculum(product_dict['curriculum']),
            'learner_testimonials': utils.format_testimonials(product_dict['testimonials']),
            'frequently_asked_questions': utils.format_faqs(product_dict['faqs']),
            'about_video_link': video_url,
            'end_date': product_dict['variant']['endDate'],
            'length': product_dict['durationWeeks'],
            'redirect_url': redirect_url,  # TODO: to be implemented
            'external_identifier': product_dict['id'],
            'long_description': f"{product_dict['introduction']}{product_dict['isThisCourseForYou']}",

            'title': partially_filled_csv_dict['title'],
            'short_description': partially_filled_csv_dict['title'],
            'what_will_you_learn': partially_filled_csv_dict['what_will_you_learn'],
            'verified_price': partially_filled_csv_dict['verified_price'],
            'collaborators': partially_filled_csv_dict['collaborators'],
            'prerequisites': partially_filled_csv_dict['prerequisites'],
            'additional_information': partially_filled_csv_dict['additional_information'],
            'secondary_subject': partially_filled_csv_dict['secondary_subject'],
            'tertiary_subject': partially_filled_csv_dict['tertiary_subject'],
            'start_date': partially_filled_csv_dict['start_date'],
            'minimum_effort': minimum_effort,
            'maximum_effort': maximum_effort,
        }
