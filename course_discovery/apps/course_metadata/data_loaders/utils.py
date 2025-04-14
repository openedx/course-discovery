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

from django.urls import reverse
from course_discovery.apps.course_metadata.models import CourseRunPacing, CourseRunType

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
            gspread_client = GspreadClient()  # Make sure GspreadClient is imported as needed
            return list(gspread_client.read_data(product_type_config))
        else:
            if csv_path:
                with open(csv_path, 'r') as f:
                    return list(csv.DictReader(f))
            else:
                return list(unicodecsv.DictReader(csv_file))
    except FileNotFoundError:
        logger.exception(f"Error opening CSV file at path: {csv_path}")
        raise
    except Exception as e:
        logger.exception(f"Error reading input data source: {e}")
        raise


def transform_dict_keys(data):
    """
    Transform dictionary keys to snake case.
    For example, 'Enrollment Track' becomes 'enrollment_track'.
    """
    transformed_dict = {}
    for key, value in data.items():
        updated_key = key.strip().lower().replace(' ', '_')
        transformed_dict[updated_key] = value
    return transformed_dict


def get_formatted_datetime_string(date_string):
    """
    Format a datetime string as %Y-%m-%dT%H:%M:%SZ.
    """
    return serialize_datetime(parse(date_string))


def extract_seat_prices(course_run):
    """
    Return a dictionary with seat types as keys and their prices as string values.
    Example:
        {
            "audit": "0.00",
            "verified": "100.00"
        }
    """
    prices = {}
    for seat in course_run.seats.all():
        prices[seat.type.slug] = f"{seat.price:.2f}"
    return prices

def create_course_run(api_client, data, course, course_run_type_uuid, rerun=None):
    """
    Make a course run entry through course run api.
    """
    url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"
    request_data = create_course_run_api_request_data(data, course, course_run_type_uuid, rerun)
    response = call_course_api(api_client, 'POST', url, request_data)
    if response.status_code not in (200, 201):
        logger.info(f"Course run creation response: {response.content}")
    return response.json()


def create_course_run_api_request_data(data, course, course_run_type_uuid, rerun=None):
    """
    Build the request payload for creating a course run.
    """
    course_run_creation_fields = {
        'pacing_type': get_pacing_type(data['pacing_type']),
        'start': data['start'],
        'end': data['end'],
        'run_type': str(course_run_type_uuid),
        'prices': data['prices'],
        'course': course.key,
    }
    if rerun:
        course_run_creation_fields['rerun'] = rerun
    return course_run_creation_fields


def call_course_api(api_client, method, url, data):
    """
    Helper to perform course/course run API calls.
    """
    response = api_client.request(
        method,
        url,
        json=data,
        headers={'content-type': 'application/json'}
    )
    if not response.ok:
        logger.info("API request failed for url {} with response: {}".format(url, response.content.decode('utf-8')))
    response.raise_for_status()
    return response


def get_pricing_representation(price, course_type):
    """
    Create a dictionary representation of prices for a course type.
    """
    prices = {}
    entitlement_types = course_type.entitlement_types.all()
    for entitlement_type in entitlement_types:
        prices[entitlement_type.slug] = price
    return prices


def get_pacing_type(pacing):
    """
    Map a pacing string to the corresponding CourseRunPacing value.
    """
    if pacing:
        pacing = pacing.lower()
    if pacing == 'instructor-paced':
        return CourseRunPacing.Instructor.value
    elif pacing == 'self-paced':
        return CourseRunPacing.Self.value
    else:
        return None


def get_course_run_type(course_run_type_name):
    """
    Retrieve a CourseRunType object using a cache.

    Parameters:
      - course_run_type_name: The name of the course run type.

    Returns:
      A CourseRunType instance if found, otherwise None.
    """
    try:
        return CourseRunType.objects.get(name=course_run_type_name)
    except CourseRunType.DoesNotExist:
        return None
