import concurrent.futures
import logging
import math
from decimal import Decimal
from io import BytesIO

import requests
from django.core.files import File
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Organization, Program, ProgramType, Seat, Video
)

logger = logging.getLogger(__name__)


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
        key = body['short_name']
        logo = body['logo']

        defaults = {
            'key': key,
            'partner': self.partner,
            'certificate_logo_image_url': logo,
        }

        if not self.partner.has_marketing_site:
            defaults.update({
                'name': body['name'],
                'description': body['description'],
                'logo_image_url': logo,
            })

        Organization.objects.update_or_create(key__iexact=key, partner=self.partner, defaults=defaults)
        logger.info('Processed organization "%s"', key)


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    def ingest(self):
        logger.info('Refreshing Courses and CourseRuns from %s...', self.partner.courses_api_url)

        initial_page = 1
        response = self._make_request(initial_page)
        count = response['pagination']['count']
        pages = response['pagination']['num_pages']
        self._process_response(response)

        pagerange = range(initial_page + 1, pages + 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            if self.is_threadsafe:
                for page in pagerange:
                    executor.submit(self._load_data, page)
            else:
                for future in [executor.submit(self._make_request, page) for page in pagerange]:
                    response = future.result()
                    self._process_response(response)

        logger.info('Retrieved %d course runs from %s.', count, self.partner.courses_api_url)

        self.delete_orphans()

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request(page)
        self._process_response(response)

    def _make_request(self, page):
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, username=self.username)

    def _process_response(self, response):
        results = response['results']
        logger.info('Retrieved %d course runs...', len(results))

        for body in results:
            course_run_id = body['id']

            try:
                body = self.clean_strings(body)
                course_run = self.get_course_run(body)

                if course_run:
                    self.update_course_run(course_run, body)
                    course = getattr(course_run, 'canonical_for_course', False)
                    if course:
                        course = self.update_course(course, body)
                        logger.info('Processed course with key [%s].', course.key)
                else:
                    course, created = self.get_or_create_course(body)
                    course_run = self.create_course_run(course, body)
                    if created:
                        course.canonical_course_run = course_run
                        course.save()
            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=self.partner.courses_api_url
                )
                logger.exception(msg)

    def get_course_run(self, body):
        course_run_key = body['id']
        try:
            return CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            return None

    def update_course_run(self, course_run, body):
        validated_data = self.format_course_run_data(body)
        self._update_instance(course_run, validated_data, suppress_publication=True)

        logger.info('Processed course run with UUID [%s].', course_run.uuid)

    def create_course_run(self, course, body):
        defaults = self.format_course_run_data(body, course=course)

        return CourseRun.objects.create(**defaults)

    def get_or_create_course(self, body):
        course_run_key = CourseKey.from_string(body['id'])
        course_key = self.get_course_key_from_course_run_key(course_run_key)
        defaults = self.format_course_data(body)
        # We need to add the key to the defaults because django ignores kwargs with __
        # separators when constructing the create request
        defaults['key'] = course_key
        defaults['partner'] = self.partner

        course, created = Course.objects.get_or_create(key__iexact=course_key, partner=self.partner, defaults=defaults)

        if created:
            # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
            # which may not be unique for an organization.
            key = course_run_key.org
            defaults = {'key': key}
            organization, __ = Organization.objects.get_or_create(key__iexact=key, partner=self.partner,
                                                                  defaults=defaults)

            course.authoring_organizations.add(organization)

        return (course, created)

    def update_course(self, course, body):
        validated_data = self.format_course_data(body)
        self._update_instance(course, validated_data)

        logger.info('Processed course with key [%s].', course.key)

        return course

    def _update_instance(self, instance, validated_data, **kwargs):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(**kwargs)

    def format_course_run_data(self, body, course=None):
        defaults = {
            'key': body['id'],
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'hidden': body.get('hidden', False),
        }

        # When using a marketing site, only dates (excluding start) should come from the Course API.
        if not self.partner.has_marketing_site:
            defaults.update({
                'start': self.parse_date(body['start']),
                'card_image_url': body['media'].get('image', {}).get('raw'),
                'title_override': body['name'],
                'short_description_override': body['short_description'],
                'video': self.get_courserun_video(body),
                'status': CourseRunStatus.Published,
                'pacing_type': self.get_pacing_type(body),
                'mobile_available': body.get('mobile_available') or False,
            })

        if course:
            defaults['course'] = course

        return defaults

    def format_course_data(self, body):
        defaults = {
            'title': body['name'],
        }

        return defaults

    def get_pacing_type(self, body):
        pacing = body.get('pacing')

        if pacing:
            pacing = pacing.lower()

        if pacing == 'instructor':
            return CourseRunPacing.Instructor
        elif pacing == 'self':
            return CourseRunPacing.Self
        else:
            return None

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video, __ = Video.objects.get_or_create(src=video_url)

        return video


class EcommerceApiDataLoader(AbstractDataLoader):
    """ Loads course seats from the E-Commerce API. """

    def ingest(self):
        logger.info('Refreshing course seats from %s...', self.partner.ecommerce_api_url)

        initial_page = 1
        response = self._make_request(initial_page)
        count = response['count']
        pages = math.ceil(count / self.PAGE_SIZE)
        self._process_response(response)

        pagerange = range(initial_page + 1, pages + 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            if self.is_threadsafe:
                for page in pagerange:
                    executor.submit(self._load_data, page)
            else:
                for future in [executor.submit(self._make_request, page) for page in pagerange]:
                    response = future.result()
                    self._process_response(response)

        logger.info('Retrieved %d course seats from %s.', count, self.partner.ecommerce_api_url)

        self.delete_orphans()

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request(page)
        self._process_response(response)

    def _make_request(self, page):
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, include_products=True)

    def _process_response(self, response):
        results = response['results']
        logger.info('Retrieved %d course seats...', len(results))

        for body in results:
            body = self.clean_strings(body)
            self.update_seats(body)

    def update_seats(self, body):
        course_run_key = body['id']
        try:
            course_run = CourseRun.objects.get(key__iexact=course_run_key)
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
        sku = stock_record['partner_sku']

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
            'sku': sku,
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
    image_width = 1440
    image_height = 480
    XSERIES = None

    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(ProgramsApiDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )
        self.XSERIES = ProgramType.objects.get(name='XSeries')

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

    def _get_uuid(self, body):
        return body['uuid']

    def update_program(self, body):
        uuid = self._get_uuid(body)

        try:
            defaults = {
                'uuid': uuid,
                'title': body['name'],
                'subtitle': body['subtitle'],
                'type': self.XSERIES,
                'status': body['status'],
                'banner_image_url': self._get_banner_image_url(body),
            }

            program, __ = Program.objects.update_or_create(
                marketing_slug=body['marketing_slug'],
                partner=self.partner,
                defaults=defaults
            )
            self._update_program_organizations(body, program)
            self._update_program_courses_and_runs(body, program)
            self._update_program_banner_image(body, program)
            program.save()
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to load program %s', uuid)

    def _update_program_courses_and_runs(self, body, program):
        course_run_keys = set()
        for course_code in body.get('course_codes', []):
            course_run_keys.update([course_run['course_key'] for course_run in course_code['run_modes']])

        # The course_code key field is technically useless, so we must build the course list from the
        # associated course runs.
        courses = Course.objects.filter(course_runs__key__in=course_run_keys).distinct()
        program.courses.clear()
        program.courses.add(*courses)

        # Do a diff of all the course runs and the explicitly-associated course runs to determine
        # which course runs should be explicitly excluded.
        excluded_course_runs = CourseRun.objects.filter(course__in=courses).exclude(key__in=course_run_keys)
        program.excluded_course_runs.clear()
        program.excluded_course_runs.add(*excluded_course_runs)

    def _update_program_organizations(self, body, program):
        uuid = self._get_uuid(body)
        org_keys = [org['key'] for org in body['organizations']]
        organizations = Organization.objects.filter(key__in=org_keys, partner=self.partner)

        if len(org_keys) != organizations.count():
            logger.error('Organizations for program [%s] are invalid!', uuid)

        program.authoring_organizations.clear()
        program.authoring_organizations.add(*organizations)

    def _get_banner_image_url(self, body):
        image_key = 'w{width}h{height}'.format(width=self.image_width, height=self.image_height)
        image_url = body.get('banner_image_urls', {}).get(image_key)
        return image_url

    def _update_program_banner_image(self, body, program):
        image_url = self._get_banner_image_url(body)
        if not image_url:
            logger.warning('There are no banner image url for program %s', program.title)
            return

        r = requests.get(image_url)
        if r.status_code == 200:
            banner_downloaded = File(BytesIO(r.content))
            program.banner_image.save(
                'banner.jpg',
                banner_downloaded
            )
            program.save()
        else:
            logger.exception('Loading the banner image %s for program %s failed', image_url, program.title)
