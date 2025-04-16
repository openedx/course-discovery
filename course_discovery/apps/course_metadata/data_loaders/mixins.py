"""Mixins related to Data Loaders"""
import logging
from abc import ABC, abstractmethod
from functools import cache

from dateutil.parser import parse
from django.conf import settings
from django.urls import reverse

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun, CourseRunPacing, CourseRunType

logger = logging.getLogger(__name__)


class DataLoaderMixin(ABC):
    """
    Mixin having all the commonly used utility functions for data loaders.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not hasattr(self, 'api_client') or self.api_client is None:
            raise ValueError("api_client must be set before using DataLoaderMixin.")

    @staticmethod
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

    @staticmethod
    def get_formatted_datetime_string(date_string):
        """
        Return the datetime string into the desired format %Y-%m-%dT%H:%M:%SZ
        """
        return serialize_datetime(parse(date_string)) if date_string else None

    @staticmethod
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

    def create_course_run(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Make a course run entry through course run api.
        """
        url = f"{settings.DISCOVERY_BASE_URL}{reverse('api:v1:course_run-list')}"
        request_data = self.create_course_run_api_request_data(data, course, course_type, course_run_type_uuid, rerun)
        response = self.call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run creation response: {response.content}")
        return response.json()

    def create_course_run_api_request_data(self, data, course, course_type, course_run_type_uuid, rerun=None):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course run creation via course run api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type)
        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['course_pacing']),
            'start': self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}"),
            'end': self.get_formatted_datetime_string(f"{data['end_date']} {data['end_time']}"),
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
            'course': course.key,
        }

        if rerun:
            course_run_creation_fields['rerun'] = rerun
        return course_run_creation_fields

    def call_course_api(self, method, url, data):
        """
        Helper method to make course and course run api calls.
        """
        response = self.api_client.request(
            method,
            url,
            json=data,
            headers={'content-type': 'application/json'}
        )
        if not response.ok:
            logger.info("API request failed for url %s with response: %s", url, response.content.decode('utf-8'))
        response.raise_for_status()
        return response

    @staticmethod
    def get_pacing_type(pacing):
        """
        Return appropriate pacing selection against a provided pacing string.
        """
        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor-paced':
            return CourseRunPacing.Instructor.value
        elif pacing == 'self-paced':
            return CourseRunPacing.Self.value
        else:
            return None

    @staticmethod
    @cache
    def get_course_run_type(course_run_type_name):
        """
        Retrieve a CourseRunType object, using a cache to avoid redundant queries.

        Args:
            course_run_type_name (str): Course run type name
        """
        try:
            return CourseRunType.objects.get(name=course_run_type_name)
        except CourseRunType.DoesNotExist:
            return None

    @staticmethod
    def get_pricing_representation(price, course_type):
        """
        Return dict representation of prices for a given course type.
        """
        prices = {}
        entitlement_types = course_type.entitlement_types.all()
        for entitlement_type in entitlement_types:
            prices.update({entitlement_type.slug: price})
        return prices

    @staticmethod
    def get_course_key(organization_key, number):
        """
        Given organization key and course number, return course key.
        """
        return '{org}+{number}'.format(org=organization_key, number=number)

    def create_course(self, data, course_type, course_run_type_uuid, product_source=None):
        """
        Make a course entry through course api.
        """
        course_api_url = reverse('api:v1:course-list')
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}"

        request_data = self.create_course_api_request_data(data, course_type, course_run_type_uuid, product_source)
        response = self.call_course_api('POST', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course creation response: {response.content}")
        return response.json()

    def create_course_api_request_data(self, data, course_type, course_run_type_uuid, product_source=None):
        """
        Given a data dictionary, return a reduced data representation in dict
        which will be used as input for course creation via course api.
        """
        pricing = self.get_pricing_representation(data['verified_price'], course_type)
        product_source_slug = product_source.slug if product_source else None

        course_run_creation_fields = {
            'pacing_type': self.get_pacing_type(data['course_pacing']),
            'start': self.get_formatted_datetime_string(f"{data['start_date']} {data['start_time']}"),
            'end': self.get_formatted_datetime_string(f"{data['end_date']} {data['end_time']}"),
            'run_type': str(course_run_type_uuid),
            'prices': pricing,
        }

        return {
            'org': data['organization'],
            'title': data['title'],
            'number': data['number'],
            'product_source': product_source_slug,
            'type': str(course_type.uuid),
            'prices': pricing,
            'course_run': course_run_creation_fields
        }

    def update_course(self, course_data, course, is_draft):
        """
        Update the course data.
        """
        course_api_url = reverse('api:v1:course-detail', kwargs={'key': course.uuid})
        url = f"{settings.DISCOVERY_BASE_URL}{course_api_url}?exclude_utm=1"
        request_data = self.update_course_api_request_data(course_data, course, is_draft)
        response = self.call_course_api('PATCH', url, request_data)

        if response.status_code not in (200, 201):
            logger.info(f"Course update response: {response.content}")
        return response.json()

    def update_course_run(self, course_run_data, course_run, course_type, is_draft):
        """
        Update the course run data.
        """
        course_run_api_url = reverse('api:v1:course_run-detail', kwargs={'key': course_run.key})
        url = f"{settings.DISCOVERY_BASE_URL}{course_run_api_url}?exclude_utm=1"
        request_data = self.update_course_run_api_request_data(course_run_data, course_run, course_type, is_draft)
        response = self.call_course_api('PATCH', url, request_data)
        if response.status_code not in (200, 201):
            logger.info(f"Course run update response: {response.content}")
        return response.json()

    @abstractmethod
    def update_course_api_request_data(self, course_data, course, is_draft):
        """Update the course API request data based on the course and draft state."""

    @abstractmethod
    def update_course_run_api_request_data(self, course_run_data, course_run, course_type, is_draft):
        """Update the course run API request data based on the run, type, and draft state."""

    @staticmethod
    def get_draft_flag(course):
        """
        To keep behavior consistent with publisher, draft flag is false only when:
            1. Course run is moved from Unpublished -> Review State
            2. Any of the Course run is in published state
        No 1 is not applicable at the moment as we are changing status via data loaders, so we are sending false
        draft flag to the course_run api directly for now.
        """
        return not CourseRun.objects.filter_drafts(course=course, status=CourseRunStatus.Published).exists()

    @staticmethod
    def add_product_source(course, product_source):
        """
        Associate product source object with provided course object.
        """
        course.product_source = product_source
        if course.official_version:
            course.official_version.product_source = product_source
            course.official_version.save(update_fields=['product_source'])
        course.save(update_fields=['product_source'])
