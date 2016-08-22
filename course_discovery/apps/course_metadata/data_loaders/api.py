import logging
from decimal import Decimal
from io import BytesIO

import requests
from django.core.files import File
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Video, Organization, Seat, CourseRun, Program, Course, ProgramType,
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
        defaults = {
            'key': key,
            'name': body['name'],
            'description': body['description'],
            'logo_image_url': body['logo'],
            'partner': self.partner,
        }
        Organization.objects.update_or_create(key__iexact=key, defaults=defaults)
        logger.info('Processed organization "%s"', key)


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
        course_run_key = CourseKey.from_string(body['id'])
        course_key = self.get_course_key_from_course_run_key(course_run_key)

        defaults = {
            'key': course_key,
            'title': body['name'],
        }
        course, created = Course.objects.get_or_create(key__iexact=course_key, partner=self.partner, defaults=defaults)

        if created:
            # NOTE (CCB): Use the data from the CourseKey since the Course API exposes display names for org and number,
            # which may not be unique for an organization.
            key = course_run_key.org
            defaults = {'key': key}
            organization, __ = Organization.objects.get_or_create(key__iexact=key, partner=self.partner,
                                                                  defaults=defaults)
            course.authoring_organizations.add(organization)

        logger.info('Processed course with key [%s].', course_key)
        return course

    def update_course_run(self, course, body):
        key = body['id']
        defaults = {
            'key': key,
            'start': self.parse_date(body['start']),
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'pacing_type': self.get_pacing_type(body),
        }

        # When using a marketing site, only date and pacing information should come from the Course API
        if not self.partner.has_marketing_site:
            defaults.update({
                'card_image_url': body['media'].get('image', {}).get('raw'),
                'title_override': body['name'],
                'short_description_override': body['short_description'],
                'video': self.get_courserun_video(body),
            })

        course_run, __ = course.course_runs.update_or_create(key__iexact=key, defaults=defaults)

        logger.info('Processed course run with key [%s].', course_run.key)
        return course_run

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

    def get_courserun_video(self, body):
        video = None
        video_url = body['media'].get('course_video', {}).get('uri')

        if video_url:
            video, __ = Video.objects.get_or_create(src=video_url)

        return video


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
    image_width = 1440
    image_height = 480
    XSERIES = None

    def __init__(self, partner, api_url, access_token=None, token_type=None):
        super(ProgramsApiDataLoader, self).__init__(partner, api_url, access_token, token_type)
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
