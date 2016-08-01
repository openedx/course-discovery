""" Data loaders. """
import abc
import logging
from decimal import Decimal
from urllib.parse import urljoin

import html2text
from dateutil.parser import parse
from django.utils.functional import cached_property
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.utils import delete_orphans
from course_discovery.apps.course_metadata.models import (
    Course, CourseOrganization, CourseRun, Image, LanguageTag, LevelType, Organization, Person, Seat, Subject, Video,
    Program,
)

logger = logging.getLogger(__name__)


class AbstractDataLoader(metaclass=abc.ABCMeta):
    """ Base class for all data loaders.

    Attributes:
        api_url (str): URL of the API from which data is loaded
        partner (Partner): Partner which owns the data for this data loader
        access_token (str): OAuth2 access token
        PAGE_SIZE (int): Number of items to load per API call
    """

    PAGE_SIZE = 50
    SUPPORTED_TOKEN_TYPES = ('bearer', 'jwt',)

    def __init__(self, partner, api_url, access_token, token_type):
        """
        Arguments:
            partner (Partner): Partner which owns the APIs and data being loaded
            api_url (str): URL of the API from which data is loaded
            access_token (str): OAuth2 access token
            token_type (str): The type of access token passed in (e.g. Bearer, JWT)
        """
        token_type = token_type.lower()

        if token_type not in self.SUPPORTED_TOKEN_TYPES:
            raise ValueError('The token type {token_type} is invalid!'.format(token_type=token_type))

        self.access_token = access_token
        self.token_type = token_type
        self.partner = partner
        self.api_url = api_url

    @cached_property
    def api_client(self):
        """
        Returns an authenticated API client ready to call the API from which data is loaded.

        Returns:
            EdxRestApiClient
        """
        kwargs = {}

        if self.token_type == 'jwt':
            kwargs['jwt'] = self.access_token
        else:
            kwargs['oauth_access_token'] = self.access_token

        return EdxRestApiClient(self.api_url, **kwargs)

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

    @classmethod
    def delete_orphans(cls):
        """ Remove orphaned objects from the database. """
        for model in (Image, Person, Video):
            delete_orphans(model)


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        api_url = self.partner.organizations_api_url
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s...', api_url)

        while page:
            response = self.api_client.organizations().get(page=page, page_size=self.PAGE_SIZE)
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

        logger.info('Retrieved %d organizations from %s.', count, api_url)

        self.delete_orphans()

    def update_organization(self, body):
        image = None
        image_url = body['logo']
        if image_url:
            image, __ = Image.objects.get_or_create(src=image_url)
        defaults = {
            'name': body['name'],
            'description': body['description'],
            'logo_image': image,
            'partner': self.partner,
        }
        Organization.objects.update_or_create(key=body['short_name'], defaults=defaults)
        logger.info('Created/updated organization "%s"', body['short_name'])


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    def ingest(self):
        api_url = self.partner.courses_api_url
        count = None
        page = 1

        logger.info('Refreshing Courses and CourseRuns from %s...', api_url)

        while page:
            response = self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE)
            count = response['pagination']['count']
            results = response['results']
            logger.info('Retrieved %d course runs...', len(results))

            if response['pagination']['next']:
                page += 1
            else:
                page = None

            for body in results:
                course_run_id = body['id']

                try:
                    body = self.clean_strings(body)
                    course = self.update_course(body)
                    self.update_course_run(course, body)
                except:  # pylint: disable=bare-except
                    msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                        course_run=course_run_id,
                        api_url=api_url
                    )
                    logger.exception(msg)

        logger.info('Retrieved %d course runs from %s.', count, api_url)

        self.delete_orphans()

    def update_course(self, body):
        # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
        # which may not be unique for an organization.
        course_run_key_str = body['id']
        course_run_key = CourseKey.from_string(course_run_key_str)
        organization, __ = Organization.objects.get_or_create(key=course_run_key.org,
                                                              defaults={'partner': self.partner})
        course_key = self.convert_course_run_key(course_run_key_str)
        defaults = {
            'title': body['name'],
            'partner': self.partner,
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
            image, __ = Image.objects.get_or_create(src=image_url)

        return image

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video, __ = Video.objects.get_or_create(src=video_url)

        return video


class DrupalApiDataLoader(AbstractDataLoader):
    """Loads course runs from the Drupal API."""

    def ingest(self):
        api_url = self.partner.marketing_site_api_url
        logger.info('Refreshing Courses and CourseRuns from %s...', api_url)
        response = self.api_client.courses.get()

        data = response['items']
        logger.info('Retrieved %d course runs...', len(data))

        for body in data:
            # NOTE (CCB): Some of the entries are empty arrays. We will fix this on the Drupal side of things
            # later (ECOM-4493). For now, ignore them.
            if not body:
                continue

            course_run_id = body['course_id']
            try:
                cleaned_body = self.clean_strings(body)
                course = self.update_course(cleaned_body)
                self.update_course_run(course, cleaned_body)
            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=api_url
                )
                logger.exception(msg)

        # Clean Organizations separately from other orphaned instances to avoid removing all orgnaziations
        # after an initial data load on an empty table.
        Organization.objects.filter(courseorganization__isnull=True).delete()
        self.delete_orphans()

        logger.info('Retrieved %d course runs from %s.', len(data), api_url)

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
        course.partner = self.partner

        level_type, __ = LevelType.objects.get_or_create(name=body['level']['title'])
        course.level_type = level_type

        self.set_subjects(course, body)
        self.set_sponsors(course, body)

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

    def set_sponsors(self, course, body):
        """Update `course` with sponsors from `body`."""
        course.courseorganization_set.filter(relation_type=CourseOrganization.SPONSOR).delete()
        for sponsor_body in body['sponsors']:
            image, __ = Image.objects.get_or_create(src=sponsor_body['image'])
            defaults = {
                'name': sponsor_body['title'],
                'logo_image': image,
                'homepage_url': urljoin(self.partner.marketing_site_url_root, sponsor_body['uri']),
            }
            organization, __ = Organization.objects.update_or_create(key=sponsor_body['uuid'], defaults=defaults)
            CourseOrganization.objects.create(
                course=course,
                organization=organization,
                relation_type=CourseOrganization.SPONSOR
            )

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
        course_run.marketing_url = urljoin(self.partner.marketing_site_url_root, body['course_about_uri'])
        course_run.start = self.parse_date(body['start'])
        course_run.end = self.parse_date(body['end'])

        self.set_staff(course_run, body)

        course_run.save()
        return course_run

    def set_staff(self, course_run, body):
        """Update `course_run` with staff from `body`."""
        course_run.staff.clear()
        for staff_body in body['staff']:
            image, __ = Image.objects.get_or_create(src=staff_body['image'])
            defaults = {
                'name': staff_body['title'],
                'profile_image': image,
                'title': staff_body['display_position']['title'],
            }
            person, __ = Person.objects.update_or_create(key=staff_body['uuid'], defaults=defaults)
            course_run.staff.add(person)

    def get_language_tag(self, body):
        """Get a language tag from Drupal data given by `body`."""
        iso_code = body['current_language']
        if iso_code is None:
            return None

        # NOTE (CCB): Default to U.S. English for edx.org to avoid spewing
        # unnecessary warnings.
        if iso_code == 'en':
            iso_code = 'en-us'

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
        api_url = self.partner.ecommerce_api_url
        count = None
        page = 1

        logger.info('Refreshing course seats from %s...', api_url)

        while page:
            response = self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, include_products=True)
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

        logger.info('Retrieved %d course seats from %s.', count, api_url)

        self.delete_orphans()

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


class ProgramsApiDataLoader(AbstractDataLoader):
    """ Loads programs from the Programs API. """
    image_width = 435
    image_height = 145

    def ingest(self):
        api_url = self.partner.programs_api_url
        count = None
        page = 1

        logger.info('Refreshing programs from %s...', api_url)

        while page:
            response = self.api_client.programs.get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d programs...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for program in results:
                program = self.clean_strings(program)
                self.update_program(program)

        logger.info('Retrieved %d programs from %s.', count, api_url)

    def update_program(self, body):
        uuid = body['uuid']

        try:
            defaults = {
                'title': body['name'],
                'subtitle': body['subtitle'],
                'category': body['category'],
                'status': body['status'],
                'marketing_slug': body['marketing_slug'],
                'image': self._get_image(body),
                'partner': self.partner,
            }

            program, __ = Program.objects.update_or_create(uuid=uuid, defaults=defaults)

            organizations = []
            for org in body['organizations']:
                organization, __ = Organization.objects.get_or_create(
                    key=org['key'], defaults={'name': org['display_name'], 'partner': self.partner}
                )
                organizations.append(organization)

            program.organizations.clear()
            program.organizations.add(*organizations)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to load program %s', uuid)

    def _get_image(self, body):
        image = None
        image_key = 'w{width}h{height}'.format(width=self.image_width, height=self.image_height)
        image_url = body.get('banner_image_urls', {}).get(image_key)

        if image_url:
            defaults = {
                'width': self.image_width,
                'height': self.image_height,
            }
            image, __ = Image.objects.update_or_create(src=image_url, defaults=defaults)

        return image
