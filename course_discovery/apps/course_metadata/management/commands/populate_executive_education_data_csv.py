"""
Management command to provide an output data CSV using data from Product API and an optional input partially filled csv.
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
    help = 'Transform Product API data into a CSV Data Loader compatible CSV'

    # The list to define order of the header keys in csv.
    OUTPUT_CSV_HEADERS = [
        '2u_organization_code', 'title', '2u_title', 'edx_title', 'number',
        'alternate_number', 'course_enrollment_track', 'image', 'short_description', 'long_description',
        'what_will_you_learn', 'course_level', 'primary_subject', '2u_primary_subject', 'subject_subcategory',
        'verified_price', 'collaborators', 'syllabus', 'prerequisites', 'learner_testimonials',
        'frequently_asked_questions', 'additional_information', 'about_video_link', 'secondary_subject',
        'tertiary_subject', 'course_embargo_(ofac)_restriction_text_added_to_the_faq_section', 'publish_date',
        'start_date', 'start_time', 'end_date', 'end_time', 'reg_close_date', 'reg_close_time',
        'course_run_enrollment_track', 'course_pacing', 'staff', 'minimum_effort', 'maximum_effort', 'length',
        'content_language', 'transcript_language', 'expected_program_type', 'expected_program_name',
        'upgrade_deadline_override_date', 'upgrade_deadline_override_time', 'redirect_url', 'external_identifier',
        'lead_capture_form_url', 'certificate_header', 'certificate_text', 'stat1', 'stat1_text', 'stat2',
        'stat2_text', 'organic_url', 'organization_short_code_override', 'variant_id',
    ]

    # Mapping English and Spanish languages to IETF equivalent variants
    LANGUAGE_MAP = {
        'English': 'English - United States',
        'Español': 'Spanish - Spain (Modern)',
    }

    MISSING_CSV_PRODUCT_MESSAGE = "[MISSING PRODUCT IN CSV] Unable to find product details for product {} in CSV"
    SUCCESS_MESSAGE = "Data population and transformation completed for CSV row title {}"

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth_token',
            dest='auth_token',
            type=str,
            help='Bearer token for making API calls to Product API'
        )
        parser.add_argument(
            '--output_csv',
            dest='output_csv',
            type=str,
            required=True,
            help='Path of the output CSV'
        )
        parser.add_argument(
            '--input_csv',
            dest='input_csv',
            type=str,
            required=False,
            help='Path to partially filled input CSV'
        )
        parser.add_argument(
            '--dev_input_json',
            dest='dev_input_json',
            type=str,
            required=False,
            help='Path to JSON file containing the product details, only meant for development usage/purposes'
        )

    def handle(self, *args, **options):
        input_csv = options.get('input_csv')
        output_csv = options.get('output_csv')
        auth_token = options.get('auth_token')
        dev_input_json = options.get('dev_input_json')

        if not (dev_input_json or auth_token):
            raise CommandError(
                "auth_token or dev_input_json should be provided to perform data transformation."
            )

        # Error/Warning messages to be displayed at the end of population
        self.messages_list = []  # pylint: disable=attribute-defined-outside-init

        if input_csv:
            try:
                input_reader = csv.DictReader(open(input_csv, 'r'))  # lint-amnesty, pylint: disable=consider-using-with
                input_reader = list(input_reader)
            except FileNotFoundError:
                raise CommandError(  # pylint: disable=raise-missing-from
                    "Error opening csv file at path {}".format(input_csv)
                )
        else:
            input_reader = []

        if dev_input_json:
            products = self.mock_product_details(dev_input_json)
        else:
            products = self.get_product_details(auth_token)

        if not products:
            raise CommandError("Unexpected error occurred while fetching products")

        with open(output_csv, 'w', newline='') as output_writer:

            output_writer = self.write_csv_header(output_writer)

            for product in products:
                if input_reader:
                    row = [row_item for row_item in input_reader if product['name'] == row_item['Title']]
                    if not row or len(row) != 1:
                        self.messages_list.append(self.MISSING_CSV_PRODUCT_MESSAGE.format(product['name']))
                        row = {}
                    else:
                        row = self.transform_dict_keys(row[0])
                else:
                    row = {}

                output_dict = self.get_transformed_data(row, product)
                output_writer = self.write_csv_row(output_writer, output_dict)
                logger.info(self.SUCCESS_MESSAGE.format(product['name']))  # lint-amnesty, pylint: disable=logging-format-interpolation

            logger.info("Data Transformation has completed. Warnings raised during the transformation:")
            for message in self.messages_list:
                logger.warning(message)

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

    def clean_data_dict(self, data):
        """
        Return a cleaned version of data dictionary where the null/None values are replaced
        with empty strings.
        """
        product_dict = {}
        for key, value in data.items():
            # Recursively clean the nested dictionaries
            if isinstance(value, dict):
                product_dict[key] = self.clean_data_dict(value)
            elif value is not None:
                product_dict[key] = value
            else:
                product_dict[key] = ''
        return product_dict

    def get_product_details(self, auth_token):
        """
        Method to get all products from provided product API.
        """
        url = settings.PRODUCT_API_URL
        # TODO: Remove User-agent once product API's 403 error is resolved.
        headers = {
            "Authorization": f"Bearer {auth_token}",
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'
        }
        params = {
            "detail": 1
        }

        try:
            response = requests.get(url, headers=headers, params=params)  # pylint: disable=missing-timeout
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

    def mock_product_details(self, input_json_path):
        """
        Dev Helper method to read response from file to ease development process.
        """
        with open(input_json_path, 'r') as f:
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
        try:
            minimum_effort, maximum_effort = utils.format_effort_info(product_dict['effort'])
        except Exception:  # pylint: disable=broad-except
            # Exception is raised for the cases where the effort field has value in Spanish
            # Defaulting to 1,2 for such cases
            self.messages_list.append("Invalid effort value '{}' detected for course title {}".format(
                product_dict['effort'],
                product_dict['name']
            ))
            minimum_effort, maximum_effort = 1, 2

        language = self.LANGUAGE_MAP.get(product_dict['language'], 'English - United States')

        default_values = {  # the values that will be part of every output row in any case
            'course_enrollment_track': 'Executive Education(2U)',
            'course_run_enrollment_track': 'Unpaid Executive Education',
            'start_time': '00:00:00',
            'end_time': '23:59:59',
            'reg_close_time': '23:59:59',
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
        product_dict = self.clean_data_dict(product_dict)
        stats = product_dict['stats']

        return {
            **default_values,
            'organization_short_code_override': product_dict['altUniversityAbbreviation'],
            '2u_organization_code': product_dict['universityAbbreviation'],
            'number': product_dict['abbreviation'],
            'alternate_number': product_dict['altAbbreviation'],
            'image': utils.format_base64_strings(product_dict['cardUrl']),
            'primary_subject': product_dict['altSubjectMatter'],
            '2u_primary_subject': product_dict['subjectMatter'],
            'subject_subcategory': product_dict['altSubjectMatter1'],
            'syllabus': utils.format_curriculum(product_dict['curriculum']),
            'learner_testimonials': utils.format_testimonials(product_dict['testimonials']),
            'frequently_asked_questions': utils.format_faqs(product_dict['faqs']),
            'about_video_link': utils.format_base64_strings(product_dict['videoURL']),
            'variant_id': product_dict['variant']['id'],
            'end_date': product_dict['variant']['endDate'],
            'length': product_dict['durationWeeks'],
            'redirect_url': utils.format_base64_strings(product_dict.get('edxPlpUrl', '')),
            'external_identifier': product_dict['id'],
            'long_description': f"{product_dict['introduction']}{product_dict['isThisCourseForYou']}",
            'lead_capture_form_url': utils.format_base64_strings(product_dict['lcfURL']),
            'certificate_header': product_dict['certificate'].get('headline', ''),
            'certificate_text': product_dict['certificate'].get('blurb', ''),
            'stat1': stats['stat1'],
            'stat1_text': stats['stat1Blurb'],
            'stat2': stats['stat2'],
            'stat2_text': stats['stat2Blurb'],
            'organic_url': utils.format_base64_strings(product_dict.get('edxRedirectUrl', '')),

            'title': partially_filled_csv_dict.get('title') or product_dict['altName'] or product_dict['name'],
            '2u_title': product_dict['name'],
            'edx_title': product_dict['altName'],
            'short_description': product_dict.get('blurb') or product_dict.get('name'),
            'what_will_you_learn': product_dict['whatWillSetYouApart'] or partially_filled_csv_dict.get(
                'what_will_you_learn'
            ),
            'verified_price': partially_filled_csv_dict.get('verified_price') or product_dict['variant']['finalPrice'],
            'collaborators': partially_filled_csv_dict.get('collaborators', ''),
            'prerequisites': partially_filled_csv_dict.get('prerequisites', ''),
            'additional_information': partially_filled_csv_dict.get('additional_information', ''),
            'secondary_subject': partially_filled_csv_dict.get('secondary_subject', ''),
            'tertiary_subject': partially_filled_csv_dict.get('tertiary_subject', ''),
            'start_date': partially_filled_csv_dict.get('start_date') or product_dict['variant']['startDate'],
            'reg_close_date': partially_filled_csv_dict.get('regCloseDate') or product_dict['variant']['regCloseDate'],
            'minimum_effort': minimum_effort,
            'maximum_effort': maximum_effort,
        }
