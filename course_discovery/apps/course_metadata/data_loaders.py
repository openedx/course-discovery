""" Data loaders. """
import abc
import logging
from decimal import Decimal
from urllib.parse import urljoin

from dateutil.parser import parse
from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient
import html2text
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.models import (
    Course, CourseOrganization, CourseRun, Image, LanguageTag, LevelType, Organization, Seat, Subject, Video
)

logger = logging.getLogger(__name__)


class AbstractDataLoader(metaclass=abc.ABCMeta):
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        access_token (str): OAuth2 access token
        PAGE_SIZE (int): Number of items to load per API call
    """

    PAGE_SIZE = 50

    def __init__(self, api_url, access_token=None):
        """
        Arguments:
            api_url (str): URL of the API from which data is loaded
            access_token (str): OAuth2 access token
        """
        self.access_token = access_token
        self.api_url = api_url

    @abc.abstractmethod
    def ingest(self):  # pragma: no cover
        """ Load data for all supported objects (e.g. courses, runs). """
        pass

    @classmethod
    def clean_string(cls, s):
        """ Removes all leading and trailing spaces. Returns None if the resulting string is empty. """
        if not isinstance(s, str):
            return s

        return s.strip() or None

    @classmethod
    def clean_strings(cls, data):
        """ Iterates over all string values, removing leading and trailing spaces,
        and replacing empty strings with None. """
        return {k: cls.clean_string(v) for k, v in data.items()}

    @classmethod
    def parse_date(cls, date_string):
        """
        Returns a parsed date.

        Args:
            date_string (str): String to be parsed.

        Returns:
            datetime, or None
        """
        if date_string:
            return parse(date_string)

        return None

    @classmethod
    def convert_course_run_key(cls, course_run_key_str):
        """
        Given a serialized course run key, return the corresponding
        serialized course key.

        Args:
            course_run_key_str (str): The serialized course run key.

        Returns:
            str
        """
        course_run_key = CourseKey.from_string(course_run_key_str)
        return '{org}+{course}'.format(org=course_run_key.org, course=course_run_key.course)


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s...', self.api_url)

        while page:
            response = client.organizations().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d organizations...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                self.update_organization(body)

        logger.info('Retrieved %d organizations from %s.', count, self.api_url)

    def update_organization(self, body):
        image = None
        image_url = body['logo']
        if image_url:
            image_url = image_url.lower()
            image, __ = Image.objects.get_or_create(src=image_url)
        defaults = {
            'name': body['name'],
            'description': body['description'],
            'logo_image': image,
        }
        Organization.objects.update_or_create(key=body['short_name'], defaults=defaults)


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing Courses and CourseRuns from %s...', self.api_url)

        while page:
            response = client.courses().get(page=page, page_size=self.PAGE_SIZE)
            count = response['pagination']['count']
            results = response['results']
            logger.info('Retrieved %d course runs...', len(results))

            if response['pagination']['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                course = self.update_course(body)
                self.update_course_run(course, body)

        logger.info('Retrieved %d course runs from %s.', count, self.api_url)

    def update_course(self, body):
        # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
        # which may not be unique for an organization.
        course_run_key_str = body['id']
        course_run_key = CourseKey.from_string(course_run_key_str)
        organization, __ = Organization.objects.get_or_create(key=course_run_key.org)
        course_key = self.convert_course_run_key(course_run_key_str)
        defaults = {
            'title': body['name']
        }
        course, __ = Course.objects.update_or_create(key=course_key, defaults=defaults)

        course.organizations.clear()
        CourseOrganization.objects.create(
            course=course, organization=organization, relation_type=CourseOrganization.OWNER)

        return course

    def update_course_run(self, course, body):
        defaults = {
            'course': course,
            'start': self.parse_date(body['start']),
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'title': body['name'],
            'short_description': body['short_description'],
            'video': self.get_courserun_video(body),
            'pacing_type': self.get_pacing_type(body),
            'image': self.get_courserun_image(body),
        }
        CourseRun.objects.update_or_create(key=body['id'], defaults=defaults)

    def get_pacing_type(self, body):
        pacing = body.get('pacing')

        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor':
            return CourseRun.INSTRUCTOR_PACED
        elif pacing == 'self':
            return CourseRun.SELF_PACED
        else:
            return None

    def get_courserun_image(self, body):
        image = None
        image_url = body['media'].get('image', {}).get('raw')

        if image_url:
            image_url = image_url.lower()
            image, __ = Image.objects.get_or_create(src=image_url)

        return image

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video_url = video_url.lower()
            video, __ = Video.objects.get_or_create(src=video_url)

        return video


class DrupalApiDataLoader(AbstractDataLoader):
    """Loads course runs from the Drupal API."""

    def ingest(self):
        client = EdxRestApiClient(self.api_url)
        logger.info('Refreshing Courses and CourseRuns from %s...', self.api_url)
        response = client.courses.get()

        data = response['items']
        logger.info('Retrieved %d course runs...', len(data))

        for body in data:
            cleaned_body = self.clean_strings(body)
            course = self.update_course(cleaned_body)
            self.update_course_run(course, cleaned_body)

        logger.info('Retrieved %d course runs from %s.', len(data), self.api_url)

    def update_course(self, body):
        """Create or update a course from Drupal data given by `body`."""
        course_key = self.convert_course_run_key(body['course_id'])
        try:
            course = Course.objects.get(key=course_key)
        except Course.DoesNotExist:
            logger.warning('Course not find course [%s]', course_key)
            return None

        course.full_description = self.clean_html(body['description'])
        course.short_description = self.clean_html(body['subtitle'])
        course.marketing_url = urljoin(settings.MARKETING_URL_ROOT, body['course_about_uri'])

        level_type, __ = LevelType.objects.get_or_create(name=body['level']['title'])
        course.level_type = level_type

        self.set_subjects(course, body)

        course.save()
        return course

    def set_subjects(self, course, body):
        """Update `course` with subjects from `body`."""
        course.subjects.clear()
        subjects = (s['title'] for s in body['subjects'])
        for subject_name in subjects:
            # Normalize subject names with title case
            subject, __ = Subject.objects.get_or_create(name=subject_name.title())
            course.subjects.add(subject)

    def update_course_run(self, course, body):
        """
        Create or update a run of `course` from Drupal data given by `body`.
        """
        course_run_key = body['course_id']
        try:
            course_run = CourseRun.objects.get(key=course_run_key)
        except CourseRun.DoesNotExist:
            logger.warning('Could not find course run [%s]', course_run_key)
            return None
        course_run.language = self.get_language_tag(body)
        course_run.course = course
        course_run.save()
        return course_run

    def get_language_tag(self, body):
        """Get a language tag from Drupal data given by `body`."""
        iso_code = body['current_language']
        if iso_code is None:
            return None
        try:
            return LanguageTag.objects.get(code=iso_code)
        except LanguageTag.DoesNotExist:
            logger.warning('Could not find language with ISO code [%s].', iso_code)
            return None

    def clean_html(self, content):
        """Cleans HTML from a string and returns a Markdown version."""
        stripped = content.replace('&nbsp;', '')
        html_converter = html2text.HTML2Text()
        html_converter.wrap_links = False
        html_converter.body_width = None
        return html_converter.handle(stripped).strip()


class EcommerceApiDataLoader(AbstractDataLoader):
    """ Loads course seats from the E-Commerce API. """

    def ingest(self):
        client = EdxRestApiClient(self.api_url, oauth_access_token=self.access_token)
        count = None
        page = 1

        logger.info('Refreshing course seats from %s...', self.api_url)

        while page:
            response = client.courses().get(page=page, page_size=self.PAGE_SIZE, include_products=True)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d course seats...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for body in results:
                body = self.clean_strings(body)
                self.update_seats(body)

        logger.info('Retrieved %d course seats from %s.', count, self.api_url)

    def update_seats(self, body):
        course_run_key = body['id']
        try:
            course_run = CourseRun.objects.get(key=course_run_key)
        except CourseRun.DoesNotExist:
            logger.warning('Could not find course run [%s]', course_run_key)
            return None

        for product_body in body['products']:
            if product_body['structure'] != 'child':
                continue
            product_body = self.clean_strings(product_body)
            self.update_seat(course_run, product_body)

        # Remove seats which no longer exist for that course run
        certificate_types = [self.get_certificate_type(product) for product in body['products']
                             if product['structure'] == 'child']
        course_run.seats.exclude(type__in=certificate_types).delete()

    def update_seat(self, course_run, product_body):
        stock_record = product_body['stockrecords'][0]
        currency_code = stock_record['price_currency']
        price = Decimal(stock_record['price_excl_tax'])

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            logger.warning("Could not find currency [%s]", currency_code)
            return None

        attributes = {attribute['name']: attribute['value'] for attribute in product_body['attribute_values']}

        seat_type = attributes.get('certificate_type', Seat.AUDIT)
        credit_provider = attributes.get('credit_provider')

        credit_hours = attributes.get('credit_hours')
        if credit_hours:
            credit_hours = int(credit_hours)

        defaults = {
            'price': price,
            'upgrade_deadline': self.parse_date(product_body.get('expires')),
            'credit_hours': credit_hours,
        }

        course_run.seats.update_or_create(type=seat_type, credit_provider=credit_provider, currency=currency,
                                          defaults=defaults)

    def get_certificate_type(self, product):
        return next(
            (att['value'] for att in product['attribute_values'] if att['name'] == 'certificate_type'),
            Seat.AUDIT
        )
