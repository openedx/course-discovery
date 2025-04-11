"""
Utils for loaders to format or transform field values.
"""
import csv
import base64
import logging
import re

from lxml.html import clean
from django.conf import settings
import unicodecsv
from dateutil.parser import parse
from course_discovery.apps.course_metadata.data_loaders.constants import CSVIngestionErrorMessages, CSVIngestionErrors

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import OrganizationMapping
from course_discovery.apps.course_metadata.validators import HtmlValidator

logger = logging.getLogger(__name__)


class HtmlCleaner():
    """
    Custom html cleaner inline with validator rules.
    """

    def __init__(self):
        ALLOWED_TAGS = HtmlValidator.ALLOWED_TAGS
        ALLOWED_ATTRS = HtmlValidator.ALLOWED_ATTRS
        ALLOWED_TAG_ATTRS = HtmlValidator.ALLOWED_TAG_ATTRS

        for attribs in ALLOWED_TAG_ATTRS.values():
            ALLOWED_ATTRS = ALLOWED_ATTRS.union(attribs)

        self.cleaner = clean.Cleaner(
            safe_attrs_only=True,
            safe_attrs=frozenset(ALLOWED_ATTRS),
            allow_tags=ALLOWED_TAGS
        )


cleaner = HtmlCleaner().cleaner


def p_tag(text):
    """
    Convert text string into html p tag
    """
    return f"<p>{text}</p>"


def format_faqs(data):
    """
    Format list of faqs as one html text string.
    """
    formatted_html = ""
    for faq in data:
        headline = faq['headline']
        blurb = faq['blurb']
        formatted_html += p_tag(f"<b>{headline}</b>") + blurb

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html


def format_curriculum(data):
    """
    Format list of modules in curriculum as one html text string.
    """
    formatted_html = ""
    if 'blurb' in data:
        blurb = data['blurb']
        formatted_html = p_tag(blurb) if blurb else ""

    if 'modules' in data:
        for modules in data['modules']:
            heading = modules['heading']
            description = modules['description'].strip()
            formatted_html += p_tag(f"<b>{heading}: </b>{description}")

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html


def format_testimonials(data):
    """
    Format list of testimonials as one html text string.
    """
    formatted_html = ""
    for testimonial in data:
        name = testimonial['name']
        title = testimonial['title']
        text = testimonial['text']
        formatted_html += p_tag(f"<i>\"{text}\"</i>") + p_tag(f"-{name} ({title})")

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html


def format_effort_info(data):
    """
    Format the effort info in the form of maximum and minimum effort
    """
    if len(data) > 0:
        temp = re.findall(r'\d+', data)
        effort_vals = tuple(map(int, temp))
        if len(effort_vals) == 1:
            effort_vals = (effort_vals[0], effort_vals[0] + 1)
        return effort_vals
    return None


def format_base64_strings(data):
    """
    Decode and returns the encoded base64 strings if encoded
    """
    try:
        return base64.b64decode(data).decode('utf-8')
    except Exception:  # pylint: disable=broad-except
        return data


def map_external_org_code_to_internal_org_code(external_org_code, product_source):
    """
    Map external organization code to internal organization code if it exists in OrganizationMapping table else
    return the external organization code.

    Keyword Arguments:
        external_org_code (str): External organization code
        product_source (str): Product source slug

    Returns:
        str: Internal organization code if it exists in OrganizationMapping table else return external organization
    """
    org_mapping = OrganizationMapping.objects.filter(
        organization_external_key=external_org_code,
        source__slug=product_source
    )
    if org_mapping:
        logger.info(
            f'Found corresponding internal organization against external org_code {external_org_code} and '
            f'product_source {product_source}'
        )
        return org_mapping.first().organization.key
    else:
        logger.warning(
            f'No internal organization found against external org_code {external_org_code} and '
            f'product_source {product_source}'
        )
        return external_org_code

def initialize_csv_reader(csv_path, csv_file, use_gspread_client, product_type=None, product_source=None):
    """
    Initialize the CSV reader based on the input source (csv_path, csv_file or gspread_client)
    """
    try:
        if use_gspread_client:
            product_type_config = settings.PRODUCT_METADATA_MAPPING[product_type][product_source.slug]
            gspread_client = GspreadClient()
            return list(gspread_client.read_data(product_type_config))
        else:
            # read the file from the provided path; otherwise, use the file received from CSVDataLoaderConfiguration
            return list(csv.DictReader(open(csv_path, 'r'))) if csv_path else list(unicodecsv.DictReader(csv_file))
    except FileNotFoundError:
        logger.exception(f"Error opening CSV file at path: {csv_path}")
        raise
    except Exception as e:
        logger.exception(f"Error reading input data source: {e}")
        raise

def transform_dict_keys(data):
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

def get_formatted_datetime_string(date_string):
    """
    Return the datetime string into the desired format %Y-%m-%dT%H:%M:%SZ
    """
    return serialize_datetime(parse(date_string))

def _validate_and_process_row(self, row, course_title, org_key=None):
    """
    Validate the row data and process the row if it is valid.

    Args:
        row (dict): course data row
        course_title (str): Course title
        org_key (str): Organization key

    Returns:
        bool: True if the row is valid, False otherwise
        CourseType: CourseType object
        CourseRunType: CourseRunType object
    """
    if org_key and not self.validate_organization(org_key, course_title):
        return False, None, None

    def validate_course_and_course_run_types(row, course_title):
        """
        Helper method to validate course and course run types.

        Args:
            row (dict): Course data row
            course_title (str): Course title

        Returns:
            bool: True if course and course run types are valid, False otherwise
            CourseType: CourseType object
            CourseRunType: CourseRunType object
        """
        course_type = self.get_course_type(row["course_enrollment_track"])
        if not course_type:
            self._log_ingestion_error(
                CSVIngestionErrors.MISSING_COURSE_TYPE,
                CSVIngestionErrorMessages.MISSING_COURSE_TYPE.format(
                    course_title=course_title, course_type=row["course_enrollment_track"]
                ),
            )
            return False, None, None

        course_run_type = self.get_course_run_type(row["course_run_enrollment_track"])
        if not course_run_type:
            self._log_ingestion_error(
                CSVIngestionErrors.MISSING_COURSE_RUN_TYPE,
                CSVIngestionErrorMessages.MISSING_COURSE_RUN_TYPE.format(
                    course_title=course_title, course_run_type=row["course_run_enrollment_track"]
                ),
            )
            return False, None, None

        return True, course_type, course_run_type

    is_valid, course_type, course_run_type = validate_course_and_course_run_types(row, course_title)
    if not is_valid:
        return False, course_type, course_run_type

    missing_fields = self.validate_course_data(course_type, row)
    if missing_fields:
        self._log_ingestion_error(
            CSVIngestionErrors.MISSING_REQUIRED_DATA,
            CSVIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                course_title=course_title, missing_data=missing_fields
            )
        )
        return False, course_type, course_run_type

    return True, course_type, course_run_type

def extract_seat_prices(course_run):
    prices = {}
    for seat in course_run.seats:
        prices[seat.type] = seat.price
    return prices
