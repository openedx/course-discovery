import concurrent.futures
import logging
import math
import threading
import time
from decimal import Decimal
from io import BytesIO

import backoff
import requests
from django.conf import settings
from django.core.files import File
from django.core.management import CommandError
from django.db.models import Q
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.course_type import calculate_course_type
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, CourseRunType, CourseType, Organization, Program, ProgramType, Seat, SeatType,
    Video
)
from course_discovery.apps.course_metadata.utils import push_to_ecommerce_for_course_run, subtract_deadline_delta

logger = logging.getLogger(__name__)


def _fatal_code(ex):
    """
    Give up if the error indicates that the request was invalid.

    That means don't retry any 4XX code, except 429, which is rate limiting.
    """
    return (
        ex.response is not None and
        ex.response.status_code != 429 and
        400 <= ex.response.status_code < 500
    )  # pylint: disable=no-member


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
                    response = future.result()
                    self._process_response(response)

        logger.info('Retrieved %d course runs from %s.', count, self.partner.courses_api_url)

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request(page)
        self._process_response(response)

    # The courses endpoint has a 40 requests/minute rate limit.
    # This will back off at a rate of 60/120/240 seconds (from the factor 60 and default value of base 2).
    # This backoff code can still fail because of the concurrent requests all requesting at the same time.
    # So even in the case of entering into the next minute, if we still exceed our limit for that min,
    # any requests that failed in both limits are still approaching their max_tries limit.
    @backoff.on_exception(
        backoff.expo,
        factor=60,
        max_tries=4,
        exception=requests.exceptions.RequestException,
        giveup=_fatal_code,
    )
    def _make_request(self, page):
        logger.info('Requesting course run page %d...', page)
        params = {'page': page, 'page_size': self.PAGE_SIZE, 'username': self.username}
        response = self.api_client.get(self.api_url + '/courses/', params=params)
        response.raise_for_status()
        return response.json()

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

        validated_data = self.format_course_run_data(body)
        end_has_updated = validated_data.get('end') != run.end
        self._update_instance(official_run, validated_data, suppress_publication=True)
        self._update_instance(draft_run, validated_data, suppress_publication=True)
        if end_has_updated:
            self._update_verified_deadline_for_course_run(official_run)
            self._update_verified_deadline_for_course_run(draft_run)
            has_upgrade_deadline_override = run.seats.filter(upgrade_deadline_override__isnull=False)
            if not has_upgrade_deadline_override and official_run:
                push_to_ecommerce_for_course_run(official_run)

        logger.info('Processed course run with UUID [%s].', run.uuid)

    def create_course_run(self, course, body):
        defaults = self.format_course_run_data(body, course=course)

        # Set type to be the same as the most recent run as a best guess.
        # Else mark the run type as empty and RCM will upgrade if it can.
        latest_run = course.course_runs.order_by('-created').first()
        if latest_run and latest_run.type:
            defaults['type'] = latest_run.type
        else:
            defaults['type'] = CourseRunType.objects.get(slug=CourseRunType.EMPTY)

        # Course will always be an official version. But if it _does_ have a draft version, the run should too.
        if course.draft_version:
            # Start with draft version and then make official (since our utility functions expect that flow)
            defaults['course'] = course.draft_version
            draft_run = CourseRun.objects.create(**defaults, draft=True)
            return draft_run.update_or_create_official_version(notify_services=False)
        else:
            return CourseRun.objects.create(**defaults)

    def get_or_create_course(self, body):
        course_run_key = CourseKey.from_string(body['id'])
        course_key = self.get_course_key_from_course_run_key(course_run_key)
        defaults = self.format_course_data(body)
        # We need to add the key to the defaults because django ignores kwargs with __
        # separators when constructing the create request
        defaults['key'] = course_key
        defaults['partner'] = self.partner
        defaults['type'] = CourseType.objects.get(slug=CourseType.EMPTY)

        draft_version = Course.everything.filter(key__iexact=course_key, partner=self.partner, draft=True).first()
        defaults['draft_version'] = draft_version

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

    def _update_verified_deadline_for_course_run(self, course_run):
        seats = course_run.seats.filter(type=Seat.VERIFIED) if course_run and course_run.end else []
        for seat in seats:
            seat.upgrade_deadline = subtract_deadline_delta(
                seat.course_run.end, settings.PUBLISHER_UPGRADE_DEADLINE_DAYS
            )
            seat.save()

    def _update_instance(self, instance, validated_data, **kwargs):
        if not instance:
            return

        updated = False

        for attr, value in validated_data.items():
            if getattr(instance, attr) != value:
                setattr(instance, attr, value)
                updated = True

        if updated:
            instance.save(**kwargs)

    def format_course_run_data(self, body, course=None):
        defaults = {
            'key': body['id'],
            'start': self.parse_date(body['start']),
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
            'hidden': body.get('hidden', False),
            'license': body.get('license') or '',  # license cannot be None
            'title_override': body['name'],  # we support Studio edits, even though Publisher also owns titles
            'pacing_type': self.get_pacing_type(body)
        }

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

    def __init__(self, partner, api_url, max_workers=None, is_threadsafe=False, **kwargs):
        super().__init__(partner, api_url, max_workers, is_threadsafe, **kwargs)
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
        logger.info('Refreshing ecommerce data from %s...', self.partner.ecommerce_api_url)
        self._load_ecommerce_data()

        if self.processing_failure_occurred:  # pragma: no cover
            logger.warning(
                'Processing failure occurred caused by an exception on at least on of the threads, '
                'blocking deletes.'
            )
            raise CommandError('Ecommerce Data Loader failed to successfully load')
        self._delete_entitlements()

    def _load_ecommerce_data(self):
        course_runs = self._request_course_runs(self.initial_page)
        entitlements = self._request_entitlements(self.initial_page)
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
                    executor.submit(self._request_course_runs, page).add_done_callback(
                        lambda future: self._check_future_and_process(future, self._process_course_runs)
                    )
                for page in pageranges['entitlements']:
                    executor.submit(self._request_entitlements, page).add_done_callback(
                        lambda future: self._check_future_and_process(future, self.process_entitlements)
                    )
                for page in pageranges['enrollment_codes']:
                    executor.submit(self._request_enrollment_codes, page).add_done_callback(
                        lambda future: self._check_future_and_process(future, self.process_enrollment_codes)
                    )
            else:
                # Process in batches and wait for the result from the futures
                pagerange = pageranges['course_runs']
                for future in concurrent.futures.as_completed(
                    executor.submit(self._request_course_runs, page) for page in pagerange
                ):
                    self._check_future_and_process(
                        future, self._process_course_runs,
                    )

                pagerange = pageranges['entitlements']
                for future in concurrent.futures.as_completed(
                    executor.submit(self._request_entitlements, page) for page in pagerange
                ):
                    self._check_future_and_process(
                        future, self._process_entitlements,
                    )

                pagerange = pageranges['enrollment_codes']
                for future in concurrent.futures.as_completed(
                    executor.submit(self._request_enrollment_codes, page) for page in pagerange
                ):
                    self._check_future_and_process(
                        future, self._process_enrollment_codes,
                    )

        logger.info('Expected %d course seats, %d course entitlements, and %d enrollment codes from %s.',
                    course_runs['count'], entitlements['count'],
                    enrollment_codes['count'], self.partner.ecommerce_api_url)

        logger.info('Actually Received %d course seats, %d course entitlements, and %d enrollment codes from %s.',
                    self.course_run_count,
                    self.entitlement_count,
                    self.enrollment_code_count,
                    self.partner.ecommerce_api_url)

        # Try to upgrade empty run types to real ones, now that we have seats from ecommerce
        empty_course_type = CourseType.objects.get(slug=CourseType.EMPTY)
        empty_course_run_type = CourseRunType.objects.get(slug=CourseRunType.EMPTY)
        has_empty_type = (Q(type=empty_course_type, course_runs__seats__isnull=False) |
                          Q(course_runs__type=empty_course_run_type, course_runs__seats__isnull=False))
        for course in Course.everything.filter(has_empty_type, partner=self.partner).distinct().iterator():
            if not calculate_course_type(course, commit=True):
                logger.warning('Calculating course type failure occurred for [%s].', course)
                self.processing_failure_occurred = True

        if (self.course_run_count != course_runs['count'] or
                self.entitlement_count != entitlements['count'] or
                self.enrollment_code_count != enrollment_codes['count']):  # pragma: no cover
            # The count expected should match the count received
            logger.warning('There is a mismatch in the expected count of results and the actual results.')
            self.processing_failure_occurred = True

    def _pagerange(self, count):
        pages = int(math.ceil(count / self.PAGE_SIZE))
        return range(self.initial_page + 1, pages + 1)

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=5
    )
    def _request_course_runs(self, page):
        params = {'page': page, 'page_size': self.PAGE_SIZE, 'include_products': True}
        return self.api_client.get(self.api_url + '/courses/', params=params).json()

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=5
    )
    def _request_entitlements(self, page):
        params = {'page': page, 'page_size': self.PAGE_SIZE, 'product_class': 'Course Entitlement'}
        return self.api_client.get(self.api_url + '/products/', params=params).json()

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_tries=5
    )
    def _request_enrollment_codes(self, page):
        params = {'page': page, 'page_size': self.PAGE_SIZE, 'product_class': 'Enrollment Code'}
        return self.api_client.get(self.api_url + '/products/', params=params).json()

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

    def _check_future_and_process(self, future, process_fn):
        check_exception = future.exception()
        if check_exception is None:
            response = future.result()
            process_fn(response)
        else:
            logger.exception(check_exception)
            # Protect against deletes if exceptions occurred
            self.processing_failure_occurred = True

    def update_seats(self, body):
        course_run_key = body['id']
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

        seats_to_remove = course_run.seats.exclude(type__slug__in=certificate_types)
        if seats_to_remove.count() > 0:
            logger.info(
                'Removing seats [%s] for course run with key [%s].',
                ', '.join(s.type.slug for s in seats_to_remove),
                course_run_key,
            )
        seats_to_remove.delete()

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
            msg = ('Could not find seat type {seat_type} while loading seat with sku {sku} for course run with key '
                   '{key}'.format(seat_type=certificate_type, sku=sku, key=course_run.key))
            logger.warning(msg)
            self.processing_failure_occurred = True
            return
        if not course_run.type.empty and not course_run.type.tracks.filter(seat_type=seat_type).exists():
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

        _, created = course_run.seats.update_or_create(
            type=seat_type,
            credit_provider=credit_provider,
            currency=currency,
            defaults=defaults
        )

        if created:
            logger.info('Created seat for course with key [%s] and sku [%s].', course_run.key, sku)

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
        if not course.type.empty and mode not in course.type.entitlement_types.all():
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

    def __init__(self, partner, api_url, max_workers=None, is_threadsafe=False):
        super().__init__(partner, api_url, max_workers, is_threadsafe)
        self.XSERIES = ProgramType.objects.get(translations__name_t='XSeries')

    def ingest(self):
        api_url = self.partner.programs_api_url
        count = None
        page = 1

        logger.info('Refreshing programs from %s...', api_url)

        while page:
            params = {'page': page, 'page_size': self.PAGE_SIZE}
            response = self.api_client.get(self.api_url + '/programs/', params=params).json()
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
        image_key = f'w{self.image_width}h{self.image_height}'
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
