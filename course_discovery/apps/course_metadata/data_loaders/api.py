import concurrent.futures
import logging
import math
import threading
import time
from decimal import Decimal
from io import BytesIO

import backoff
import requests
from django.core.files import File
from django.core.management import CommandError
from opaque_keys.edx.keys import CourseKey
from slumber.exceptions import HttpClientError

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, Organization, Program, ProgramType, Seat, SeatType, Video
)
from course_discovery.apps.publisher.utils import is_course_on_old_publisher

logger = logging.getLogger(__name__)


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """
    # TODO add this back in when loading from drupal is completely removed
    # loaded_org_pks = set()

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

        # TODO add this back in when loading from drupal is completely removed
        # delete_orphans(Organization, exclude=self.loaded_org_pks)

        logger.info('Removed orphan Organizations excluding those which were loaded via OrganizationsApiDataLoader')

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

        # TODO add this back in when loading from drupal is completely removed
        # if org:
        #     self.loaded_org_pks.add(org.pk)

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
        logger.info('Looping to request all %d pages...', pages)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            if self.is_threadsafe:
                for page in pagerange:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    executor.submit(self._load_data, page)
            else:
                for future in [executor.submit(self._make_request, page) for page in pagerange]:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    response = future.result()
                    self._process_response(response)

        logger.info('Retrieved %d course runs from %s.', count, self.partner.courses_api_url)

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request(page)
        self._process_response(response)

    def _fatal_code(ex):  # pylint: disable=no-self-argument
        return ex.response.status_code != 429  # pylint: disable=no-member

    # The courses endpoint has a 40 requests/minute rate limit 10/20/40 seconds puts us into the next minute
    @backoff.on_exception(
        backoff.expo,
        factor=10,
        jitter=None,
        max_tries=3,
        exception=HttpClientError,
        giveup=_fatal_code,
    )
    def _make_request(self, page):
        logger.info('Requesting course run page %d...', page)
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, username=self.username)

    def _process_response(self, response):
        results = response['results']
        logger.info('Retrieved %d course runs...', len(results))

        for body in results:
            course_run_id = body['id']

            try:
                body = self.clean_strings(body)
                official_run, draft_run = self.get_course_run(body)
                if official_run or draft_run:
                    self.update_course_run(official_run, draft_run, body)
                    if not self.partner.uses_publisher:
                        # Without publisher, we'll use Studio as the source of truth for course data
                        official_course = getattr(official_run, 'canonical_for_course', None)
                        draft_course = getattr(draft_run, 'canonical_for_course', None)
                        if official_course or draft_course:
                            self.update_course(official_course, draft_course, body)
                else:
                    course, created = self.get_or_create_course(body)
                    course_run = self.create_course_run(course, body)
                    if created:
                        course.canonical_course_run = course_run
                        course.save()
            except Exception:  # pylint: disable=broad-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=self.partner.courses_api_url
                )
                logger.exception(msg)

    def get_course_run(self, body):
        """
        Returns:
            Tuple of (official, draft) versions of the run.
        """
        course_run_key = body['id']
        run = CourseRun.objects.filter_drafts(key__iexact=course_run_key).first()
        if not run:
            return None, None
        elif run.draft:
            return run.official_version, run
        else:
            return run, run.draft_version

    def update_course_run(self, official_run, draft_run, body):
        run = draft_run or official_run
        new_pub_fe = is_course_on_old_publisher(run.course)

        validated_data = self.format_course_run_data(body, new_pub_fe=new_pub_fe)
        self._update_instance(official_run, validated_data, suppress_publication=True)
        self._update_instance(draft_run, validated_data, suppress_publication=True)

        logger.info('Processed course run with UUID [%s].', run.uuid)

    def create_course_run(self, course, body):
        new_pub_fe = is_course_on_old_publisher(course)
        defaults = self.format_course_run_data(body, course=course, new_pub_fe=new_pub_fe)

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

    def update_course(self, official_course, draft_course, body):
        validated_data = self.format_course_data(body)
        self._update_instance(official_course, validated_data)
        self._update_instance(draft_course, validated_data)

        course = official_course or draft_course
        logger.info('Processed course with key [%s].', course.key)

    def _update_instance(self, instance, validated_data, **kwargs):
        if not instance:
            return

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(**kwargs)

    def format_course_run_data(self, body, course=None, new_pub_fe=False):
        defaults = {
            'key': body['id'],
            'start': self.parse_date(body['start']),
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'hidden': body.get('hidden', False),
            'license': body.get('license') or '',  # license cannot be None
            'title_override': body['name'],  # we support Studio edits, even though Publisher also owns titles
        }

        if not self.partner.uses_publisher or new_pub_fe:
            defaults['pacing_type'] = self.get_pacing_type(body)

        if not self.partner.uses_publisher:
            defaults.update({
                'short_description_override': body['short_description'],
                'video': self.get_courserun_video(body),
                'status': CourseRunStatus.Published,
                'mobile_available': body.get('mobile_available') or False,
            })

        if course:
            defaults['course'] = course

        return defaults

    def format_course_data(self, body):
        defaults = {
            'title': body['name'],
        }

        if not self.partner.uses_publisher:
            defaults.update({
                'card_image_url': body['media'].get('image', {}).get('raw'),
            })

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
    """ Loads course seats, entitlements, and enrollment codes from the E-Commerce API. """

    LOADER_MAX_RETRY = 2

    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(EcommerceApiDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )
        self.initial_page = 1
        self.enrollment_skus = []
        self.entitlement_skus = []
        self.processing_failure_occurred = False
        self.course_run_count = 0
        self.entitlement_count = 0
        self.enrollment_code_count = 0

        # Thread locks to protect access to the counts
        self.course_run_count_lock = threading.Lock()
        self.entitlement_count_lock = threading.Lock()
        self.enrollment_code_lock = threading.Lock()

    def ingest(self):
        attempt_count = 0

        while (attempt_count == 0 or
               (self.processing_failure_occurred and attempt_count < EcommerceApiDataLoader.LOADER_MAX_RETRY)):
            attempt_count += 1
            if self.processing_failure_occurred and attempt_count > 1:  # pragma: no cover
                logger.info('Processing failure occurred attempting {attempt_count} of {max}...'.format(
                    attempt_count=attempt_count,
                    max=EcommerceApiDataLoader.LOADER_MAX_RETRY
                ))

            logger.info('Refreshing ecommerce data from %s...', self.partner.ecommerce_api_url)
            self._load_ecommerce_data()

            if self.processing_failure_occurred:  # pragma: no cover
                logger.warning('Processing failure occurred caused by an exception on at least on of the threads, '
                               'blocking deletes.')
                if attempt_count >= EcommerceApiDataLoader.LOADER_MAX_RETRY:
                    raise CommandError('Max retries exceeded and Ecommerce Data Loader failed to successfully load')
            else:
                self._delete_entitlements()

    def _load_ecommerce_data(self):
        course_runs = self._request_course_runs(self.initial_page)
        entitlements = self._request_entitlments(self.initial_page)
        enrollment_codes = self._request_enrollment_codes(self.initial_page)

        self.entitlement_skus = []
        self.enrollment_skus = []

        self.processing_failure_occurred = False
        self.course_run_count = 0
        self.entitlement_count = 0
        self.enrollment_code_count = 0
        self._process_course_runs(course_runs)
        self._process_entitlements(entitlements)
        self._process_enrollment_codes(enrollment_codes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            # Create pageranges to iterate over all existing pages for each product type
            pageranges = {
                'course_runs': self._pagerange(course_runs['count']),
                'entitlements': self._pagerange(entitlements['count']),
                'enrollment_codes': self._pagerange(enrollment_codes['count'])
            }

            if self.is_threadsafe:
                for page in pageranges['course_runs']:
                    executor.submit(self._load_course_runs_data, page)
                for page in pageranges['entitlements']:
                    executor.submit(self._load_entitlements_data, page)
                for page in pageranges['enrollment_codes']:
                    executor.submit(self._load_enrollment_codes_data, page)
            else:
                # Process in batches and wait for the result from the futures
                pagerange = pageranges['course_runs']
                for future in [executor.submit(self._request_course_runs, page) for page in pagerange]:
                    check_exception = future.exception()
                    if check_exception is None:
                        response = future.result()
                        self._process_course_runs(response)
                    else:
                        logger.exception(check_exception)
                        # Protect against deletes if exceptions occurred
                        self.processing_failure_occurred = True

                pagerange = pageranges['entitlements']
                for future in [executor.submit(self._request_entitlments, page) for page in pagerange]:
                    check_exception = future.exception()
                    if check_exception is None:
                        response = future.result()
                        self._process_entitlements(response)
                    else:
                        logger.exception(check_exception)
                        # Protect against deletes if exceptions occurred
                        self.processing_failure_occurred = True

                pagerange = pageranges['enrollment_codes']
                for future in [executor.submit(self._request_enrollment_codes, page) for page in pagerange]:
                    check_exception = future.exception()
                    if check_exception is None:
                        response = future.result()
                        self._process_enrollment_codes(response)
                    else:
                        logger.exception(check_exception)
                        # Protect against deletes if exceptions occurred
                        self.processing_failure_occurred = True

        logger.info('Expected %d course seats, %d course entitlements, and %d enrollment codes from %s.',
                    course_runs['count'], entitlements['count'],
                    enrollment_codes['count'], self.partner.ecommerce_api_url)

        logger.info('Actually Received %d course seats, %d course entitlements, and %d enrollment codes from %s.',
                    self.course_run_count,
                    self.entitlement_count,
                    self.enrollment_code_count,
                    self.partner.ecommerce_api_url)

        if (self.course_run_count != course_runs['count'] or
                self.entitlement_count != entitlements['count'] or
                self.enrollment_code_count != enrollment_codes['count']):  # pragma: no cover
            # The count expected should match the count received
            logger.warning('There is a mismatch in the expected count of results and the actual results.')
            self.processing_failure_occurred = True

    def _pagerange(self, count):
        pages = int(math.ceil(count / self.PAGE_SIZE))
        return range(self.initial_page + 1, pages + 1)

    def _load_course_runs_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        try:
            course_runs = self._request_course_runs(page)
            self._process_course_runs(course_runs)

        except requests.exceptions.RequestException as ex:
            logger.exception(ex)
            self.processing_failure_occurred = True

    def _load_entitlements_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        try:
            entitlements = self._request_entitlments(page)
            self._process_entitlements(entitlements)

        except requests.exceptions.RequestException as ex:
            logger.exception(ex)
            self.processing_failure_occurred = True

    def _load_enrollment_codes_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        try:
            enrollment_codes = self._request_enrollment_codes(page)
            self._process_enrollment_codes(enrollment_codes)
        except requests.exceptions.RequestException as ex:
            logger.exception(ex)
            self.processing_failure_occurred = True

    def _request_course_runs(self, page):
        return self.api_client.courses().get(page=page, page_size=self.PAGE_SIZE, include_products=True)

    def _request_entitlments(self, page):
        return self.api_client.products().get(page=page, page_size=self.PAGE_SIZE, product_class='Course Entitlement')

    def _request_enrollment_codes(self, page):
        return self.api_client.products().get(page=page, page_size=self.PAGE_SIZE, product_class='Enrollment Code')

    def _process_course_runs(self, response):
        results = response['results']
        logger.info('Retrieved %d course seats...', len(results))
        # Add to the collected count
        self.course_run_count_lock.acquire()
        self.course_run_count += len(results)
        self.course_run_count_lock.release()
        for body in results:
            body = self.clean_strings(body)
            self.update_seats(body)

    def _process_entitlements(self, response):
        results = response['results']
        logger.info('Retrieved %d course entitlements...', len(results))
        # Add to the collected count
        self.entitlement_count_lock.acquire()
        self.entitlement_count += len(results)
        self.entitlement_count_lock.release()

        for body in results:
            body = self.clean_strings(body)
            self.entitlement_skus.append(self.update_entitlement(body))

    def _process_enrollment_codes(self, response):
        results = response['results']
        logger.info('Retrieved %d course enrollment codes...', len(results))
        self.enrollment_code_lock.acquire()
        self.enrollment_code_count += len(results)
        self.enrollment_code_lock.release()

        for body in results:
            body = self.clean_strings(body)
            self.enrollment_skus.append(self.update_enrollment_code(body))

    def _delete_entitlements(self):
        entitlements_to_delete = CourseEntitlement.objects.filter(
            partner=self.partner
        ).exclude(sku__in=self.entitlement_skus)

        for entitlement in entitlements_to_delete:
            msg = 'Deleting entitlement for course {course_title} with sku {sku} for partner {partner}'.format(
                course_title=entitlement.course.title, sku=entitlement.sku, partner=entitlement.partner
            )
            logger.info(msg)
        entitlements_to_delete.delete()

    def update_seats(self, body):
        course_run_key = body['id']
        logger.info('Processing seats for course with key [%s].', course_run_key)
        try:
            course_run = CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            logger.warning('Could not find course run [%s]', course_run_key)
            return

        for product_body in body['products']:
            if product_body['structure'] != 'child':
                continue
            product_body = self.clean_strings(product_body)
            self.update_seat(course_run, product_body)

        # Remove seats which no longer exist for that course run
        certificate_types = [self.get_certificate_type(product) for product in body['products']
                             if product['structure'] == 'child']
        logger.info(
            'Removing seats for course with key [%s] except [%s].',
            course_run_key,
            ', '.join(certificate_types)
        )
        course_run.seats.exclude(type__slug__in=certificate_types).delete()

    def update_seat(self, course_run, product_body):
        stock_record = product_body['stockrecords'][0]
        currency_code = stock_record['price_currency']
        price = Decimal(stock_record['price_excl_tax'])
        sku = stock_record['partner_sku']

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            logger.warning("Could not find currency [%s]", currency_code)
            return

        attributes = {attribute['name']: attribute['value'] for attribute in product_body['attribute_values']}

        certificate_type = attributes.get('certificate_type', Seat.AUDIT)
        try:
            seat_type = SeatType.objects.get(slug=certificate_type)
        except SeatType.DoesNotExist:
            msg = 'Could not find seat type {seat_type} while loading seat with sku {sku}'.format(
                seat_type=certificate_type, sku=sku
            )
            logger.warning(msg)
            self.processing_failure_occurred = True
            return
        if course_run.type and not course_run.type.tracks.filter(seat_type=seat_type).exists():
            logger.warning(
                'Seat type {seat_type} is not compatible with course run type {run_type} for course run {key}'.format(
                    seat_type=seat_type.slug, run_type=course_run.type.slug, key=course_run.key,
                )
            )
            self.processing_failure_occurred = True
            return

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

        course_run.seats.update_or_create(
            type=seat_type,
            credit_provider=credit_provider,
            currency=currency,
            defaults=defaults
        )

        logger.info('Processed seat for course with key [%s] and sku [%s].', course_run.key, sku)

    def validate_stockrecord(self, stockrecords, title, product_class):
        """
        Argument:
            body (dict): product data from ecommerce, either entitlement or enrollment code
        Returns:
            product sku if no exceptions, else None
        """
        # Map product_class keys with how they should be displayed in the exception messages.
        product_classes = {
            'entitlement': {
                'name': 'entitlement',
                'value': 'entitlement',
            },
            'enrollment_code': {
                'name': 'enrollment_code',
                'value': 'enrollment code'
            }
        }

        try:
            product_class = product_classes[product_class]
        except (KeyError, ValueError):
            msg = 'Invalid product class of {product}. Must be entitlement or enrollment_code'.format(
                product=product_class['name']
            )
            logger.warning(msg)
            return None

        if stockrecords:
            stock_record = stockrecords[0]
        else:
            msg = '{product} product {title} has no stockrecords'.format(
                product=product_class['value'].capitalize(),
                title=title
            )
            logger.warning(msg)
            return None

        try:
            currency_code = stock_record['price_currency']
            Decimal(stock_record['price_excl_tax'])
            sku = stock_record['partner_sku']
        except (KeyError, ValueError):
            msg = 'A necessary stockrecord field is missing or incorrectly set for {product} {title}'.format(
                product=product_class['value'],
                title=title
            )
            logger.warning(msg)
            return None

        try:
            Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            msg = 'Could not find currency {code} while loading {product} {title} with sku {sku}'.format(
                product=product_class['value'], code=currency_code, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        # All validation checks passed!
        return True

    def update_entitlement(self, body):
        """
        Argument:
            body (dict): entitlement product data from ecommerce
        Returns:
            entitlement product sku if no exceptions, else None
        """
        attributes = {attribute['name']: attribute['value'] for attribute in body['attribute_values']}
        course_uuid = attributes.get('UUID')
        title = body['title']
        stockrecords = body['stockrecords']

        if not self.validate_stockrecord(stockrecords, title, 'entitlement'):
            return None

        stock_record = stockrecords[0]
        currency_code = stock_record['price_currency']
        price = Decimal(stock_record['price_excl_tax'])
        sku = stock_record['partner_sku']

        try:
            course = Course.objects.get(uuid=course_uuid)
        except Course.DoesNotExist:
            msg = 'Could not find course {uuid} while loading entitlement {title} with sku {sku}'.format(
                uuid=course_uuid, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        try:
            currency = Currency.objects.get(code=currency_code)
        except Currency.DoesNotExist:
            msg = 'Could not find currency {code} while loading entitlement {title} with sku {sku}'.format(
                code=currency_code, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        mode_name = attributes.get('certificate_type')
        try:
            mode = SeatType.objects.get(slug=mode_name)
        except SeatType.DoesNotExist:
            msg = 'Could not find mode {mode} while loading entitlement {title} with sku {sku}'.format(
                mode=mode_name, title=title, sku=sku
            )
            logger.warning(msg)
            self.processing_failure_occurred = True
            return None
        if course.type and mode not in course.type.entitlement_types.all():
            logger.warning(
                'Seat type {seat_type} is not compatible with course type {course_type} for course {uuid}'.format(
                    seat_type=mode.slug, course_type=course.type.slug, uuid=course_uuid,
                )
            )
            self.processing_failure_occurred = True
            return None

        defaults = {
            'partner': self.partner,
            'price': price,
            'currency': currency,
            'sku': sku,
        }
        msg = 'Creating entitlement {title} with sku {sku} for partner {partner}'.format(
            title=title, sku=sku, partner=self.partner
        )
        logger.info(msg)
        course.entitlements.update_or_create(mode=mode, defaults=defaults)
        return sku

    def update_enrollment_code(self, body):
        """
        Argument:
            body (dict): enrollment code product data from ecommerce
        Returns:
            enrollment code product sku if no exceptions, else None
        """
        attributes = {attribute['code']: attribute['value'] for attribute in body['attribute_values']}
        course_key = attributes.get('course_key')
        title = body['title']
        stockrecords = body['stockrecords']

        if not self.validate_stockrecord(stockrecords, title, "enrollment_code"):
            return None

        stock_record = stockrecords[0]
        sku = stock_record['partner_sku']

        try:
            course_run = CourseRun.objects.get(key=course_key)
        except CourseRun.DoesNotExist:
            msg = 'Could not find course run {key} while loading enrollment code {title} with sku {sku}'.format(
                key=course_key, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        seat_type = attributes.get('seat_type')
        try:
            Seat.objects.get(course_run=course_run, type=seat_type)
        except Seat.DoesNotExist:
            msg = 'Could not find seat type {type} while loading enrollment code {title} with sku {sku}'.format(
                type=seat_type, title=title, sku=sku
            )
            logger.warning(msg)
            return None

        defaults = {
            'bulk_sku': sku
        }
        msg = 'Creating enrollment code {title} with sku {sku} for partner {partner}'.format(
            title=title, sku=sku, partner=self.partner
        )
        logger.info(msg)

        course_run.seats.update_or_create(type=seat_type, defaults=defaults)
        return sku

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
