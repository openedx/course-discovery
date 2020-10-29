import datetime
import json
from decimal import Decimal
from unittest import mock

import ddt
import pytz
import responses
from django.core.management import CommandError
from django.http.response import HttpResponse
from django.test import TestCase
from edx_django_utils.cache import TieredCache
from pytz import UTC
from slumber.exceptions import HttpClientError

from course_discovery.apps.core.tests.utils import mock_api_callback, mock_jpeg_callback
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.api import (
    AbstractDataLoader, CoursesApiDataLoader, EcommerceApiDataLoader, ProgramsApiDataLoader, _fatal_code
)
from course_discovery.apps.course_metadata.data_loaders.tests import JPEG, JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, CourseRunType, CourseType, Organization, Program, ProgramType, Seat, SeatType
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEntitlementFactory, CourseFactory, CourseRunFactory, OrganizationFactory, SeatFactory, SeatTypeFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.api.logger'


class AbstractDataLoaderTest(TestCase):
    def test_clean_string(self):
        """ Verify the method leading and trailing spaces, and returns None for empty strings. """
        # Do nothing for non-string input
        self.assertIsNone(AbstractDataLoader.clean_string(None))
        self.assertEqual(AbstractDataLoader.clean_string(3.14), 3.14)

        # Return None for empty strings
        self.assertIsNone(AbstractDataLoader.clean_string(''))
        self.assertIsNone(AbstractDataLoader.clean_string('    '))
        self.assertIsNone(AbstractDataLoader.clean_string('\t'))

        # Return the stripped value for non-empty strings
        for s in ('\tabc', 'abc', ' abc ', 'abc ', '\tabc\t '):
            self.assertEqual(AbstractDataLoader.clean_string(s), 'abc')

    def test_parse_date(self):
        """ Verify the method properly parses dates. """
        # Do nothing for empty values
        self.assertIsNone(AbstractDataLoader.parse_date(''))
        self.assertIsNone(AbstractDataLoader.parse_date(None))

        # Parse datetime strings
        dt = datetime.datetime.utcnow()
        self.assertEqual(AbstractDataLoader.parse_date(dt.isoformat()), dt)


@ddt.ddt
class CoursesApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = CoursesApiDataLoader

    @property
    def api_url(self):
        return self.partner.courses_api_url

    def mock_api(self, bodies=None):
        if not bodies:
            bodies = mock_data.COURSES_API_BODIES
        url = self.api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies, pagination=True),
            content_type=JSON
        )
        return bodies

    def test_fatal_code(self):
        response_with_200 = HttpResponse(status=200)
        response_with_400 = HttpResponse(status=400)
        response_with_429 = HttpResponse(status=429)
        response_with_504 = HttpResponse(status=504)
        self.assertFalse(_fatal_code(HttpClientError(response=response_with_200)))
        self.assertTrue(_fatal_code(HttpClientError(response=response_with_400)))
        self.assertFalse(_fatal_code(HttpClientError(response=response_with_429)))
        self.assertFalse(_fatal_code(HttpClientError(response=response_with_504)))

    def assert_course_run_loaded(self, body, partner_uses_publisher=True, draft=False, new_pub=False):
        """ Assert a CourseRun corresponding to the specified data body was properly loaded into the database. """

        # Validate the Course
        course_key = '{org}+{key}'.format(org=body['org'], key=body['number'])
        organization = Organization.objects.get(key=body['org'])
        course = Course.everything.get(key=course_key, draft=draft)

        self.assertListEqual(list(course.authoring_organizations.all()), [organization])

        # Validate the course run
        course_run = course.course_runs.get(key=body['id'])
        expected_values = {
            'start': self.loader.parse_date(body['start']),
            'end': self.loader.parse_date(body['end']),
            'enrollment_start': self.loader.parse_date(body['enrollment_start']),
            'enrollment_end': self.loader.parse_date(body['enrollment_end']),
            'card_image_url': None,
            'title_override': body['name'],
            'short_description_override': None,
            'video': None,
            'hidden': body.get('hidden', False),
            'license': body.get('license', ''),
        }

        if not partner_uses_publisher or new_pub:
            expected_values['pacing_type'] = self.loader.get_pacing_type(body)

        if not partner_uses_publisher:
            expected_values.update({
                'card_image_url': None,
                'short_description_override': self.loader.clean_string(body['short_description']),
                'video': self.loader.get_courserun_video(body),
                'status': CourseRunStatus.Published,
                'pacing_type': self.loader.get_pacing_type(body),
                'mobile_available': body['mobile_available'] or False,
            })

            # Check if the course card_image_url was correctly updated
            self.assertEqual(course.card_image_url, body['media'].get('image', {}).get('raw'),)

        for field, value in expected_values.items():
            self.assertEqual(getattr(course_run, field), value, f'Field {field} is invalid.')

        return course_run

    @responses.activate
    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    )
    @ddt.unpack
    def test_ingest(self, partner_uses_publisher, on_new_publisher):
        """ Verify the method ingests data from the Courses API. """
        TieredCache.dangerous_clear_all_tiers()
        api_data = self.mock_api()
        if not partner_uses_publisher:
            self.partner.publisher_url = None
            self.partner.save()

        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        # Assume that while we are relying on ORGS_ON_OLD_PUBLISHER it will never be empty
        with self.settings(ORGS_ON_OLD_PUBLISHER='MITx' if not on_new_publisher else 'OTHER'):
            self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(4)

        # Verify the CourseRuns were created correctly
        expected_num_course_runs = len(api_data)
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

        for datum in api_data:
            self.assert_course_run_loaded(datum, partner_uses_publisher, new_pub=on_new_publisher)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.data_loaders.api.push_to_ecommerce_for_course_run')
    def test_ingest_verified_deadline(self, mock_push_to_ecomm):
        """ Verify the method ingests data from the Courses API. """
        TieredCache.dangerous_clear_all_tiers()
        api_data = self.mock_api()

        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        # Assume that while we are relying on ORGS_ON_OLD_PUBLISHER it will never be empty
        with self.settings(ORGS_ON_OLD_PUBLISHER='OTHER'):
            self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(4)

        runs = CourseRun.objects.all()
        # Run with a verified entitlement, but no change in end date
        run1 = runs[0]
        run1.seats.add(SeatFactory(course_run=run1, type=SeatTypeFactory.verified()))
        run1.save()

        # Run with a verified entitlement, and the end date has changed
        run2 = runs[1]
        run2.seats.add(SeatFactory(
            course_run=run2,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=datetime.datetime.now(pytz.UTC),
        ))
        original_run2_deadline = run2.seats.first().upgrade_deadline
        run2.end = datetime.datetime.now(pytz.UTC)
        run2.save()

        # Run with a credit entitlement, and the end date has changed should not
        run3 = runs[2]
        run3.seats.add(SeatFactory(
            course_run=run3,
            type=SeatTypeFactory.credit(),
            upgrade_deadline=None,
        ))
        run3.end = datetime.datetime.now(pytz.UTC)
        run3.save()

        # Verify the CourseRuns were created correctly
        expected_num_course_runs = len(api_data)
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()
        calls = [
            mock.call(run2),
            mock.call(run3),
        ]
        mock_push_to_ecomm.assert_has_calls(calls)
        # Make sure the verified seat with a course run end date is changed
        self.assertNotEqual(original_run2_deadline, run2.seats.first().upgrade_deadline)
        # Make sure the credit seat with a course run end date is unchanged
        self.assertIsNone(run3.seats.first().upgrade_deadline)

    @responses.activate
    def test_ingest_exception_handling(self):
        """ Verify the data loader properly handles exceptions during processing of the data from the API. """
        api_data = self.mock_api()

        with mock.patch.object(self.loader, 'clean_strings', side_effect=Exception):
            with mock.patch(LOGGER_PATH) as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, len(api_data))
                msg = 'An error occurred while updating {} from {}'.format(
                    api_data[-1]['id'],
                    self.partner.courses_api_url
                )
                mock_logger.exception.assert_called_with(msg)

    @responses.activate
    @ddt.data(True, False)
    def test_ingest_canonical(self, partner_uses_publisher):
        """ Verify the method ingests data from the Courses API. """
        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.mock_api([
            mock_data.COURSES_API_BODY_ORIGINAL,
            mock_data.COURSES_API_BODY_SECOND,
            mock_data.COURSES_API_BODY_UPDATED,
        ])

        if not partner_uses_publisher:
            self.partner.publisher_url = None
            self.partner.save()

        self.loader.ingest()

        # Verify the CourseRun was created correctly by no errors raised
        course_run_orig = CourseRun.objects.get(key=mock_data.COURSES_API_BODY_ORIGINAL['id'])

        # Verify that a course has been created and set as canonical by no errors raised
        course = course_run_orig.canonical_for_course

        # Verify the CourseRun was created correctly by no errors raised
        course_run_second = CourseRun.objects.get(key=mock_data.COURSES_API_BODY_SECOND['id'])

        # Verify not set as canonical
        with self.assertRaises(AttributeError):
            course_run_second.canonical_for_course  # pylint: disable=pointless-statement

        # Verify second course not used to update course
        self.assertNotEqual(mock_data.COURSES_API_BODY_SECOND['name'], course.title)
        if partner_uses_publisher:
            # Verify the course remains unchanged by api update if we have publisher
            self.assertEqual(mock_data.COURSES_API_BODY_ORIGINAL['name'], course.title)
        else:
            # Verify updated canonical course used to update course
            self.assertEqual(mock_data.COURSES_API_BODY_UPDATED['name'], course.title)
        # Verify the updated course run updated the original course run
        self.assertEqual(mock_data.COURSES_API_BODY_UPDATED['hidden'], course_run_orig.hidden)

    def assert_run_and_course_updated(self, datum, run, exists, draft, partner_uses_publisher):
        course_key = '{org}+{number}'.format(org=datum['org'], number=datum['number'])
        run_key = datum['id']
        if run:
            self.assert_course_run_loaded(datum, partner_uses_publisher, draft=draft)
            if partner_uses_publisher and exists:  # will not update course
                self.assertNotEqual(Course.everything.get(key=course_key, draft=draft).title, datum['name'])
            else:
                self.assertEqual(Course.everything.get(key=course_key, draft=draft).title, datum['name'])
        else:
            self.assertFalse(CourseRun.everything.filter(key=run_key, draft=draft).exists())
            self.assertFalse(Course.everything.filter(key=course_key, draft=draft).exists())

    @responses.activate
    @ddt.data(
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, True),
        (True, True, False),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    )
    @ddt.unpack
    def test_ingest_handles_draft(self, official_exists, draft_exists, partner_uses_publisher):
        """
        Verify the method ingests data from the Courses API, and updates both official and draft versions.
        """
        datum = mock_data.COURSES_API_BODY_ORIGINAL
        self.mock_api([datum])

        if not partner_uses_publisher:
            self.partner.publisher_url = None
            self.partner.save()

        official_run = None
        draft_run = None

        course_key = '{org}+{number}'.format(org=datum['org'], number=datum['number'])
        run_key = datum['id']
        official_course_kwargs = {}
        official_run_kwargs = {}
        all_courses = set()
        all_runs = set()
        audit_run_type = CourseRunType.objects.get(slug=CourseRunType.AUDIT)
        if draft_exists or official_exists:
            org = OrganizationFactory(key=datum['org'])
        if draft_exists:
            draft_course = Course.objects.create(partner=self.partner, key=course_key, title='Title', draft=True)
            draft_run = CourseRun.objects.create(course=draft_course, key=run_key, type=audit_run_type, draft=True)
            draft_course.canonical_course_run = draft_run
            draft_course.save()
            draft_course.authoring_organizations.add(org)
            official_course_kwargs = {'draft_version': draft_course}
            official_run_kwargs = {'draft_version': draft_run}
            all_courses.add(draft_course)
            all_runs.add(draft_run)
        if official_exists:
            official_course = Course.objects.create(partner=self.partner, key=course_key, title='Title',
                                                    **official_course_kwargs)
            official_run = CourseRun.objects.create(course=official_course, key=run_key, type=audit_run_type,
                                                    **official_run_kwargs)
            official_course.canonical_course_run = official_run
            official_course.save()
            official_course.authoring_organizations.add(org)
            all_courses.add(official_course)
            all_runs.add(official_run)

        self.loader.ingest()

        if draft_exists or official_exists:
            self.assertEqual(set(Course.everything.all()), all_courses)
            self.assertEqual(set(CourseRun.everything.all()), all_runs)
        else:
            # We should have made official versions of the data
            official_course = Course.everything.get()
            official_run = CourseRun.everything.get()
            self.assertFalse(official_course.draft)
            self.assertFalse(official_run.draft)
            self.assertEqual(official_course.canonical_course_run, official_run)

        self.assert_run_and_course_updated(datum, draft_run, draft_exists, True, partner_uses_publisher)
        self.assert_run_and_course_updated(datum, official_run, official_exists, False, partner_uses_publisher)

    @responses.activate
    def test_ingest_studio_made_run_with_existing_draft_course(self):
        """
        Verify that we correctly stitch up a course run freshly made in Studio but with existing Publisher content.
        """
        datum = mock_data.COURSES_API_BODY_ORIGINAL
        self.mock_api([datum])

        course_key = '{org}+{number}'.format(org=datum['org'], number=datum['number'])
        Course.objects.create(partner=self.partner, key=course_key, title='Title', draft=True)

        self.loader.ingest()

        # We expect an official version of the course to be created (which points to the draft) and both a draft version
        # and official version of the course run to be created.

        draft_course = Course.everything.get(partner=self.partner, key=course_key, draft=True)
        official_course = Course.everything.get(partner=self.partner, key=course_key, draft=False)
        self.assertEqual(official_course.draft_version, draft_course)
        self.assertEqual(draft_course.course_runs.count(), 1)
        self.assertEqual(official_course.course_runs.count(), 1)

        draft_run = draft_course.course_runs.first()
        official_run = official_course.course_runs.first()
        self.assertNotEqual(draft_run, official_run)
        self.assertEqual(official_run.draft_version, draft_run)

    def test_assigns_types(self):
        """
        Verify we set the special empty course and course run types when creating courses and runs.
        And that we copy the type of the most recent run if it exists.
        """
        # First, confirm that we make new courses and runs with the empty type.
        self.mock_api([mock_data.COURSES_API_BODY_ORIGINAL])
        self.loader.ingest()

        course_run = CourseRun.objects.get(key=mock_data.COURSES_API_BODY_ORIGINAL['id'])
        self.assertIsNotNone(course_run.type)
        self.assertEqual(course_run.type.slug, CourseRunType.EMPTY)

        course = course_run.course
        self.assertIsNotNone(course.type)
        self.assertEqual(course.type.slug, CourseType.EMPTY)

        # Now confirm that we will copy the last run type if available.
        course_run.type = CourseRunType.objects.get(slug=CourseRunType.VERIFIED_AUDIT)
        course_run.save(suppress_publication=True)
        responses.reset()
        self.mock_api([mock_data.COURSES_API_BODY_SECOND])
        self.loader.ingest()

        course_run2 = CourseRun.objects.get(key=mock_data.COURSES_API_BODY_SECOND['id'])
        self.assertEqual(course_run2.type, course_run.type)

    def test_get_pacing_type_field_missing(self):
        """ Verify the method returns None if the API response does not include a pacing field. """
        self.assertIsNone(self.loader.get_pacing_type({}))

    @ddt.unpack
    @ddt.data(
        ('', None),
        ('foo', None),
        (None, None),
        ('instructor', CourseRunPacing.Instructor),
        ('Instructor', CourseRunPacing.Instructor),
        ('self', CourseRunPacing.Self),
        ('Self', CourseRunPacing.Self),
    )
    def test_get_pacing_type(self, pacing, expected_pacing_type):
        """ Verify the method returns a pacing type corresponding to the API response's pacing field. """
        self.assertEqual(self.loader.get_pacing_type({'pacing': pacing}), expected_pacing_type)

    @ddt.unpack
    @ddt.data(
        (None, None),
        ('http://example.com/image.mp4', 'http://example.com/image.mp4'),
    )
    def test_get_courserun_video(self, uri, expected_video_src):
        """ Verify the method returns an Video object with the correct URL. """
        body = {
            'media': {
                'course_video': {
                    'uri': uri
                }
            }
        }
        actual = self.loader.get_courserun_video(body)

        if expected_video_src:
            self.assertEqual(actual.src, expected_video_src)
        else:
            self.assertIsNone(actual)


@ddt.ddt
class EcommerceApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = EcommerceApiDataLoader

    @property
    def api_url(self):
        return self.partner.ecommerce_api_url

    def mock_courses_api(self):
        # Create existing seats to be removed by ingest
        audit_run_type = CourseRunType.objects.get(slug=CourseRunType.AUDIT)
        credit_run_type = CourseRunType.objects.get(slug=CourseRunType.CREDIT_VERIFIED_AUDIT)
        verified_run_type = CourseRunType.objects.get(slug=CourseRunType.VERIFIED_AUDIT)
        audit_run = CourseRunFactory(title_override='audit', key='audit/course/run', type=audit_run_type,
                                     course__partner=self.partner)
        verified_run = CourseRunFactory(title_override='verified', key='verified/course/run', type=verified_run_type,
                                        course__partner=self.partner)
        credit_run = CourseRunFactory(title_override='credit', key='credit/course/run', type=credit_run_type,
                                      course__partner=self.partner)
        no_currency_run = CourseRunFactory(title_override='no currency', key='nocurrency/course/run',
                                           type=verified_run_type, course__partner=self.partner)

        professional_type = SeatTypeFactory.professional()
        SeatFactory(course_run=audit_run, type=professional_type)
        SeatFactory(course_run=verified_run, type=professional_type)
        SeatFactory(course_run=credit_run, type=professional_type)
        SeatFactory(course_run=no_currency_run, type=professional_type)

        bodies = mock_data.ECOMMERCE_API_BODIES
        url = self.api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    def mock_products_api(self, alt_course=None, alt_currency=None, alt_mode=None, has_stockrecord=True,
                          valid_stockrecord=True, product_class=None):
        """ Return a new Course Entitlement and Enrollment Code to be added by ingest """
        course = CourseFactory(type=CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT), partner=self.partner)

        # If product_class is given, make sure it's either entitlement or enrollment_code
        if product_class:
            self.assertIn(product_class, ['entitlement', 'enrollment_code'])

        data = {
            "entitlement": {
                "count": 1,
                "num_pages": 1,
                "current_page": 1,
                "results": [
                    {
                        "structure": "child",
                        "product_class": "Course Entitlement",
                        "title": "Course Intro to Everything",
                        "price": "10.00",
                        "expires": None,
                        "attribute_values": [
                            {
                                "name": "certificate_type",
                                "value": alt_mode if alt_mode else "verified"
                            },
                            {
                                "name": "UUID",
                                "value": alt_course if alt_course else str(course.uuid)
                            }
                        ],
                        "is_available_to_buy": True,
                        "stockrecords": []
                    },
                ],
                "next": None,
                "start": 0,
                "previous": None
            },
            "enrollment_code": {
                "count": 1,
                "num_pages": 1,
                "current_page": 1,
                "results": [
                    {
                        "structure": "standalone",
                        "product_class": "Enrollment Code",
                        "title": "Course Intro to Everything",
                        "price": "10.00",
                        "expires": None,
                        "attribute_values": [
                            {
                                "code": "seat_type",
                                "value": alt_mode if alt_mode else "verified"
                            },
                            {
                                "code": "course_key",
                                "value": alt_course if alt_course else 'verified/course/run'
                            }
                        ],
                        "is_available_to_buy": True,
                        "stockrecords": []
                    }
                ],
                "next": None,
                "start": 0,
                "previous": None
            }
        }

        stockrecord = {
            "price_currency": alt_currency if alt_currency else "USD",
            "price_excl_tax": "10.00",
        }
        if valid_stockrecord:
            stockrecord.update({"partner_sku": "sku132"})
        if has_stockrecord:
            data['entitlement']['results'][0]["stockrecords"].append(stockrecord)
            data['enrollment_code']['results'][0]["stockrecords"].append(stockrecord)

        url = f'{self.api_url}products/'

        responses.add(
            responses.GET,
            '{url}?product_class={product}&page=1&page_size=50'.format(url=url, product='Course Entitlement'),
            body=json.dumps(data['entitlement']),
            content_type='application/json',
            status=200,
            match_querystring=True
        )

        responses.add(
            responses.GET,
            '{url}?product_class={product}&page=1&page_size=50'.format(url=url, product='Enrollment Code'),
            body=json.dumps(data['enrollment_code']),
            content_type='application/json',
            status=200,
            match_querystring=True
        )

        all_products = data['entitlement']['results'] + data['enrollment_code']['results']
        return all_products if product_class is None else data[product_class]['results']

    def compose_warning_log(self, alt_course, alt_currency, alt_mode, product_class):
        products = {
            "entitlement": {
                "label": "entitlement",
                "alt_course": "course",
                "alt_mode": "mode"
            },
            "enrollment_code": {
                "label": "enrollment code",
                "alt_course": "course run",
                "alt_mode": "seat type"
            }
        }

        msg = 'Could not find '
        if alt_course:
            msg += '{label} {alt_course}'.format(
                label=products[product_class]["alt_course"],
                alt_course=alt_course
            )
        elif alt_currency:
            msg += 'currency ' + alt_currency
        elif alt_mode:
            msg += '{label} {alt_mode}'.format(
                label=products[product_class]["alt_mode"],
                alt_mode=alt_mode
            )
        msg += ' while loading {product_class}'.format(product_class=products[product_class]["label"])
        msg += ' Course Intro to Everything with sku sku132'
        return msg

    def get_product_bulk_sku(self, seat_type, course_run, products):
        products = [p for p in products if p['structure'] == 'standalone']
        course_key = course_run.key
        for product in products:
            attributes = {attribute['code']: attribute['value'] for attribute in product['attribute_values']}
            if attributes['seat_type'] == seat_type and attributes['course_key'] == course_key:
                stock_record = product['stockrecords'][0]
                return stock_record['partner_sku']

        return None

    def assert_seats_loaded(self, body, mock_products):
        """ Assert a Seat corresponding to the specified data body was properly loaded into the database. """
        course_run = CourseRun.objects.get(key=body['id'])
        products = [p for p in body['products'] if p['structure'] == 'child']
        # Verify that the old seat is removed
        self.assertEqual(course_run.seats.count(), len(products))

        # Validate each seat
        for product in products:
            stock_record = product['stockrecords'][0]
            price_currency = stock_record['price_currency']
            price = Decimal(stock_record['price_excl_tax'])
            sku = stock_record['partner_sku']
            certificate_type = Seat.AUDIT
            credit_provider = None
            credit_hours = None
            if product['expires']:
                upgrade_deadline = datetime.datetime.strptime(
                    product['expires'], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=UTC)
            else:
                upgrade_deadline = None

            for att in product['attribute_values']:
                if att['name'] == 'certificate_type':
                    certificate_type = att['value']
                elif att['name'] == 'credit_provider':
                    credit_provider = att['value']
                elif att['name'] == 'credit_hours':
                    credit_hours = att['value']

            bulk_sku = self.get_product_bulk_sku(certificate_type, course_run, mock_products)
            seat = course_run.seats.get(type__slug=certificate_type, credit_provider=credit_provider,
                                        currency=price_currency)

            self.assertEqual(seat.course_run, course_run)
            self.assertEqual(seat.type.slug, certificate_type)
            self.assertEqual(seat.price, price)
            self.assertEqual(seat.currency.code, price_currency)
            self.assertEqual(seat.credit_provider, credit_provider)
            self.assertEqual(seat.credit_hours, credit_hours)
            self.assertEqual(seat.upgrade_deadline, upgrade_deadline)
            self.assertEqual(seat.sku, sku)
            self.assertEqual(seat.bulk_sku, bulk_sku)

    def assert_entitlements_loaded(self, body):
        """ Assert a Course Entitlement was loaded into the database for each entry in the specified data body. """
        body = [d for d in body if d['product_class'] == 'Course Entitlement']
        self.assertEqual(CourseEntitlement.objects.count(), len(body))
        for datum in body:
            attributes = {attribute['name']: attribute['value'] for attribute in datum['attribute_values']}
            course = Course.objects.get(uuid=attributes['UUID'])
            stock_record = datum['stockrecords'][0]
            price_currency = stock_record['price_currency']
            price = Decimal(stock_record['price_excl_tax'])
            sku = stock_record['partner_sku']

            mode_name = attributes['certificate_type']
            mode = SeatType.objects.get(slug=mode_name)

            entitlement = course.entitlements.get(mode=mode)

            self.assertEqual(entitlement.course, course)
            self.assertEqual(entitlement.price, price)
            self.assertEqual(entitlement.currency.code, price_currency)
            self.assertEqual(entitlement.sku, sku)

    def assert_enrollment_codes_loaded(self, body):
        """ Assert a Course Enrollment Code was loaded into the database for each entry in the specified data body. """
        body = [d for d in body if d['product_class'] == 'Enrollment Code']
        for datum in body:
            attributes = {attribute['code']: attribute['value'] for attribute in datum['attribute_values']}
            course_run = CourseRun.objects.get(key=attributes['course_key'])
            stock_record = datum['stockrecords'][0]
            bulk_sku = stock_record['partner_sku']

            mode_name = attributes['seat_type']
            seat = course_run.seats.get(type__slug=mode_name)

            self.assertEqual(seat.course_run, course_run)
            self.assertEqual(seat.bulk_sku, bulk_sku)

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the E-Commerce API. """
        TieredCache.dangerous_clear_all_tiers()
        courses_api_data = self.mock_courses_api()
        loaded_course_run_data = courses_api_data[:-1]
        loaded_seat_data = courses_api_data[:-2]
        self.assertEqual(CourseRun.objects.count(), len(loaded_course_run_data))

        products_api_data = self.mock_products_api()

        # Verify a seat exists on all courses already
        for course_run in CourseRun.objects.all():
            self.assertEqual(course_run.seats.count(), 1)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(4)

        for datum in loaded_seat_data:
            self.assert_seats_loaded(datum, products_api_data)

        self.assert_entitlements_loaded(products_api_data)
        self.assert_enrollment_codes_loaded(products_api_data)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

    @responses.activate
    @mock.patch(LOGGER_PATH)
    def test_ingest_deletes(self, mock_logger):
        """ Verifiy the method deletes stale data. """
        self.mock_courses_api()
        products_api_data = self.mock_products_api()
        entitlement = CourseEntitlementFactory(partner=self.partner)

        self.loader.ingest()
        # Ensure that only entitlements retrieved from the Ecommerce API remain in Discovery,
        # and that the sku and partner of the deleted entitlement are logged
        self.assert_entitlements_loaded(products_api_data)
        msg = 'Deleting entitlement for course {course_title} with sku {sku} for partner {partner}'.format(
            course_title=entitlement.course.title, sku=entitlement.sku, partner=entitlement.partner
        )
        mock_logger.info.assert_any_call(msg)

    @responses.activate
    @mock.patch(LOGGER_PATH)
    def test_no_stockrecord(self, mock_logger):
        self.mock_courses_api()
        products = self.mock_products_api(has_stockrecord=False)
        self.loader.ingest()
        msg = 'Entitlement product {entitlement} has no stockrecords'.format(entitlement=products[0]['title'])
        mock_logger.warning.assert_any_call(msg)

    @responses.activate
    @ddt.data(
        ('entitlement'),
        ('enrollment_code')
    )
    def test_invalid_stockrecord(self, product_class):
        product_classes = {
            "entitlement": "entitlement",
            "enrollment_code": "enrollment code"
        }
        self.mock_courses_api()
        products = self.mock_products_api(valid_stockrecord=False, product_class=product_class)
        with mock.patch(LOGGER_PATH) as mock_logger:
            self.loader.ingest()
            msg = 'A necessary stockrecord field is missing or incorrectly set for {product_class} {title}'.format(
                product_class=product_classes[product_class],
                title=products[0]['title']
            )
            mock_logger.warning.assert_any_call(msg)

    def test_invalid_seat_types_for_course_type(self):
        self.mock_courses_api()

        # Assign CourseType and CourseRunType values, which will conflict with the attempted verified seat type
        course_run = CourseRun.objects.get(key='verified/course/run')
        course_run.type = CourseRunType.objects.get(slug=CourseRunType.PROFESSIONAL)
        course_run.save()
        course = course_run.course
        course.type = CourseType.objects.get(slug=CourseType.PROFESSIONAL)
        course.save()

        self.mock_products_api(alt_course=str(course.uuid))

        with mock.patch(LOGGER_PATH) as mock_logger:
            with self.assertRaises(CommandError):
                self.loader.ingest()
            mock_logger.warning.assert_any_call(
                'Seat type verified is not compatible with course type professional for course {uuid}'.format(
                    uuid=course.uuid
                )
            )
            mock_logger.warning.assert_any_call(
                'Seat type verified is not compatible with course run type professional for course run {key}'.format(
                    key=course_run.key,
                )
            )

        course.refresh_from_db()
        course_run.refresh_from_db()
        self.assertEqual(course.entitlements.count(), 0)
        self.assertEqual(course_run.seats.count(), 0)

    @responses.activate
    @ddt.data(
        ('a01354b1-c0de-4a6b-c5de-ab5c6d869e76', None, None, 'entitlement', False),
        ('a01354b1-c0de-4a6b-c5de-ab5c6d869e76', None, None, 'enrollment_code', False),
        (None, "NRC", None, 'enrollment_code', False),
        (None, None, "notamode", 'entitlement', True),
        (None, None, "notamode", 'enrollment_code', True)
    )
    @ddt.unpack
    def test_ingest_fails(self, alt_course, alt_currency, alt_mode, product_class, raises):
        """ Verify the proper warnings are logged when data objects are not present. """
        self.mock_courses_api()
        self.mock_products_api(
            alt_course=alt_course,
            alt_currency=alt_currency,
            alt_mode=alt_mode,
            product_class=product_class
        )
        with mock.patch(LOGGER_PATH) as mock_logger:
            if raises:
                with self.assertRaises(CommandError):
                    self.loader.ingest()
            else:
                self.loader.ingest()
            msg = self.compose_warning_log(alt_course, alt_currency, alt_mode, product_class)
            mock_logger.warning.assert_any_call(msg)

    @ddt.unpack
    @ddt.data(
        ({"attribute_values": []}, Seat.AUDIT),
        ({"attribute_values": [{'name': 'certificate_type', 'value': 'professional'}]}, 'professional'),
        (
            {
                "attribute_values": [
                    {'name': 'other_data', 'value': 'other'},
                    {'name': 'certificate_type', 'value': 'credit'}
                ]
            },
            'credit'
        ),
        ({"attribute_values": [{'name': 'other_data', 'value': 'other'}]}, Seat.AUDIT),
    )
    def test_get_certificate_type(self, product, expected_certificate_type):
        """ Verify the method returns the correct certificate type"""
        self.assertEqual(self.loader.get_certificate_type(product), expected_certificate_type)

    @responses.activate
    def test_upgrade_empty_types(self):
        """ Verify that we try to fill in any empty course or run types after loading seats. """
        self.mock_courses_api()
        self.mock_products_api()

        # Set everything to empty, so we can upgrade them
        empty_type = CourseType.objects.get(slug=CourseType.EMPTY)
        Course.everything.update(type=empty_type)
        empty_run_type = CourseRunType.objects.get(slug=CourseRunType.EMPTY)
        CourseRun.everything.update(type=empty_run_type)

        # However, make sure we notice when a run is set, but the course is empty.
        credit_run = CourseRun.objects.get(key='credit/course/run')
        credit_run.type = CourseRunType.objects.get(slug=CourseRunType.CREDIT_VERIFIED_AUDIT)
        credit_run.save()

        # And also make sure we notice when a run is empty even though the course is not.
        # Also set it to the wrong type, to test that we fail when we can't find a match
        audit_run = CourseRun.objects.get(key='audit/course/run')
        audit_run.course.type = CourseType.objects.get(slug=CourseType.PROFESSIONAL)
        audit_run.course.save()

        with self.assertRaises(CommandError):
            self.loader.ingest()

        # Audit will have failed to match and nothing should have changed
        audit_run = CourseRun.objects.get(key='audit/course/run')
        self.assertEqual(audit_run.type.slug, CourseRunType.EMPTY)
        self.assertEqual(audit_run.course.type.slug, CourseType.PROFESSIONAL)

        verified_run = CourseRun.objects.get(key='verified/course/run')
        self.assertEqual(verified_run.type.slug, CourseRunType.VERIFIED_AUDIT)
        self.assertEqual(verified_run.course.type.slug, CourseType.VERIFIED_AUDIT)

        credit_run = CourseRun.objects.get(key='credit/course/run')
        self.assertEqual(credit_run.type.slug, CourseType.CREDIT_VERIFIED_AUDIT)
        self.assertEqual(credit_run.course.type.slug, CourseType.CREDIT_VERIFIED_AUDIT)

        # Let's fix audit's type and try again.
        audit_run.course.type = empty_type
        audit_run.course.save()
        self.loader.ingest()

        audit_run = CourseRun.objects.get(key='audit/course/run')
        self.assertEqual(audit_run.type.slug, CourseType.AUDIT)
        self.assertEqual(audit_run.course.type.slug, CourseType.AUDIT)


@ddt.ddt
class ProgramsApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = ProgramsApiDataLoader

    @property
    def api_url(self):
        return self.partner.programs_api_url

    def create_mock_organizations(self, programs):
        for program in programs:
            for organization in program.get('organizations', []):
                OrganizationFactory(key=organization['key'], partner=self.partner)

    def create_mock_courses_and_runs(self, programs):
        for program in programs:
            for course_code in program.get('course_codes', []):
                key = '{org}+{course}'.format(org=course_code['organization']['key'], course=course_code['key'])
                course = CourseFactory(key=key, partner=self.partner)

                for course_run in course_code['run_modes']:
                    CourseRunFactory(course=course, key=course_run['course_key'])

                # Add an additional course run that should be excluded
                CourseRunFactory(course=course)

    def mock_api(self):
        bodies = mock_data.PROGRAMS_API_BODIES
        self.create_mock_organizations(bodies)
        self.create_mock_courses_and_runs(bodies)

        url = self.api_url + 'programs/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )

        # We exclude the one invalid item
        return bodies[:-1]

    def assert_program_loaded(self, body):
        """ Assert a Program corresponding to the specified data body was properly loaded into the database. """
        program = Program.objects.get(uuid=AbstractDataLoader.clean_string(body['uuid']), partner=self.partner)

        self.assertEqual(program.title, body['name'])
        for attr in ('subtitle', 'status', 'marketing_slug',):
            self.assertEqual(getattr(program, attr), AbstractDataLoader.clean_string(body[attr]))

        self.assertEqual(program.type, ProgramType.objects.get(translations__name_t='XSeries'))

        keys = [org['key'] for org in body['organizations']]
        expected_organizations = list(Organization.objects.filter(key__in=keys))
        self.assertEqual(keys, [org.key for org in expected_organizations])
        self.assertListEqual(list(program.authoring_organizations.all()), expected_organizations)

        banner_image_url = body.get('banner_image_urls', {}).get('w1440h480')
        self.assertEqual(program.banner_image_url, banner_image_url)

        course_run_keys = set()
        course_codes = body.get('course_codes', [])
        for course_code in course_codes:
            course_run_keys.update([course_run['course_key'] for course_run in course_code['run_modes']])

        courses = list(Course.objects.filter(course_runs__key__in=course_run_keys).distinct().order_by('key'))
        self.assertEqual(list(program.courses.order_by('key')), courses)

        # Verify the additional course runs added in create_mock_courses_and_runs are excluded.
        self.assertEqual(program.excluded_course_runs.count(), len(course_codes))

    def assert_program_banner_image_loaded(self, body):
        """ Assert a program corresponding to the specified data body has banner image loaded into DB """
        program = Program.objects.get(uuid=AbstractDataLoader.clean_string(body['uuid']), partner=self.partner)
        banner_image_url = body.get('banner_image_urls', {}).get('w1440h480')
        if banner_image_url:
            for size_key in program.banner_image.field.variations:
                # Get different sizes specs from the model field
                # Then get the file path from the available files
                sized_image = getattr(program.banner_image, size_key, None)
                self.assertIsNotNone(sized_image)
                if sized_image:
                    path = getattr(program.banner_image, size_key).url
                    self.assertIsNotNone(path)
                    self.assertIsNotNone(program.banner_image.field.variations[size_key]['width'])
                    self.assertIsNotNone(program.banner_image.field.variations[size_key]['height'])

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the Organizations API. """
        TieredCache.dangerous_clear_all_tiers()
        api_data = self.mock_api()
        self.assertEqual(Program.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(6)

        # Verify the Programs were created correctly
        self.assertEqual(Program.objects.count(), len(api_data))

        for datum in api_data:
            self.assert_program_loaded(datum)

        self.loader.ingest()

    @responses.activate
    def test_ingest_with_missing_organizations(self):
        api_data = self.mock_api()
        Organization.objects.all().delete()

        self.assertEqual(Program.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)

        with mock.patch(LOGGER_PATH) as mock_logger:
            self.loader.ingest()
            calls = [mock.call('Organizations for program [%s] are invalid!', datum['uuid']) for datum in api_data]
            mock_logger.error.assert_has_calls(calls)

        self.assertEqual(Program.objects.count(), len(api_data))
        self.assertEqual(Organization.objects.count(), 0)

    @responses.activate
    def test_ingest_with_existing_banner_image(self):
        TieredCache.dangerous_clear_all_tiers()
        programs = self.mock_api()

        for program_data in programs:
            banner_image_url = program_data.get('banner_image_urls', {}).get('w1440h480')
            if banner_image_url:
                responses.add_callback(
                    responses.GET,
                    banner_image_url,
                    callback=mock_jpeg_callback(),
                    content_type=JPEG
                )

        self.loader.ingest()
        # Verify the API was called with the correct authorization header
        self.assert_api_called(6)

        for program in programs:
            self.assert_program_loaded(program)
            self.assert_program_banner_image_loaded(program)
