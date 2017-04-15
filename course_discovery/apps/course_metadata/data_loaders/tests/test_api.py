import datetime
from decimal import Decimal

import ddt
import mock
import responses
from django.test import TestCase
from pytz import UTC

from course_discovery.apps.core.tests.utils import mock_api_callback, mock_jpeg_callback
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.api import (
    AbstractDataLoader, CoursesApiDataLoader, EcommerceApiDataLoader, OrganizationsApiDataLoader, ProgramsApiDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import JPEG, JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import ApiClientTestMixin, DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization, Program, ProgramType, Seat
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, ImageFactory, OrganizationFactory, SeatFactory, VideoFactory
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

    def test_delete_orphans(self):
        """ Verify the delete_orphans method deletes orphaned instances. """
        instances = (ImageFactory(), VideoFactory(),)
        AbstractDataLoader.delete_orphans()

        for instance in instances:
            self.assertFalse(instance.__class__.objects.filter(pk=instance.pk).exists())  # pylint: disable=no-member

    def test_clean_html(self):
        """ Verify the method removes unnecessary HTML attributes. """
        data = (
            ('', '',),
            ('<p>Hello!</p>', 'Hello!'),
            ('<em>Testing</em>', '<em>Testing</em>'),
            ('Hello&amp;world&nbsp;!', 'Hello&world!')
        )

        for content, expected in data:
            self.assertEqual(AbstractDataLoader.clean_html(content), expected)


@ddt.ddt
class OrganizationsApiDataLoaderTests(ApiClientTestMixin, DataLoaderTestMixin, TestCase):
    loader_class = OrganizationsApiDataLoader

    @property
    def api_url(self):
        return self.partner.organizations_api_url

    def mock_api(self):
        bodies = mock_data.ORGANIZATIONS_API_BODIES
        url = self.api_url + 'organizations/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    def assert_organization_loaded(self, body, partner_has_marketing_site=True):
        """ Assert an Organization corresponding to the specified data body was properly loaded into the database. """
        organization = Organization.objects.get(key=AbstractDataLoader.clean_string(body['short_name']))
        if not partner_has_marketing_site:
            self.assertEqual(organization.name, AbstractDataLoader.clean_string(body['name']))
            self.assertEqual(organization.description, AbstractDataLoader.clean_string(body['description']))
            self.assertEqual(organization.logo_image_url, AbstractDataLoader.clean_string(body['logo']))
            self.assertEqual(organization.certificate_logo_image_url, AbstractDataLoader.clean_string(body['logo']))

    @responses.activate
    @ddt.data(True, False)
    def test_ingest(self, partner_has_marketing_site):
        """ Verify the method ingests data from the Organizations API. """
        api_data = self.mock_api()
        if not partner_has_marketing_site:
            self.partner.marketing_site_url_root = None
            self.partner.save()  # pylint: disable=no-member

        self.assertEqual(Organization.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the Organizations were created correctly
        expected_num_orgs = len(api_data)
        self.assertEqual(Organization.objects.count(), expected_num_orgs)

        for datum in api_data:
            self.assert_organization_loaded(datum, partner_has_marketing_site)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

    @responses.activate
    def test_ingest_respects_partner(self):
        """
        Existing organizations with the same key but linked to different partners
        shouldn't cause organization data loading to fail.
        """
        api_data = self.mock_api()
        key = api_data[1]['short_name']

        OrganizationFactory(key=key, partner=self.partner)
        OrganizationFactory(key=key)

        assert Organization.objects.count() == 2

        self.loader.ingest()

        assert Organization.objects.count() == len(api_data) + 1


@ddt.ddt
class CoursesApiDataLoaderTests(ApiClientTestMixin, DataLoaderTestMixin, TestCase):
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

    def assert_course_run_loaded(self, body, partner_has_marketing_site=True):
        """ Assert a CourseRun corresponding to the specified data body was properly loaded into the database. """

        # Validate the Course
        course_key = '{org}+{key}'.format(org=body['org'], key=body['number'])
        organization = Organization.objects.get(key=body['org'])
        course = Course.objects.get(key=course_key)

        self.assertEqual(course.title, body['name'])
        self.assertListEqual(list(course.authoring_organizations.all()), [organization])

        # Validate the course run
        course_run = course.course_runs.get(key=body['id'])
        expected_values = {
            'title': self.loader.clean_string(body['name']),
            'short_description': self.loader.clean_string(body['short_description']),
            'end': self.loader.parse_date(body['end']),
            'enrollment_start': self.loader.parse_date(body['enrollment_start']),
            'enrollment_end': self.loader.parse_date(body['enrollment_end']),
            'card_image_url': None,
            'title_override': None,
            'short_description_override': None,
            'video': None,
            'hidden': body.get('hidden', False),
        }

        if not partner_has_marketing_site:
            expected_values.update({
                'start': self.loader.parse_date(body['start']),
                'card_image_url': body['media'].get('image', {}).get('raw'),
                'title_override': body['name'],
                'short_description_override': self.loader.clean_string(body['short_description']),
                'video': self.loader.get_courserun_video(body),
                'status': CourseRunStatus.Published,
                'pacing_type': self.loader.get_pacing_type(body),
                'mobile_available': body['mobile_available'] or False,
            })

        for field, value in expected_values.items():
            self.assertEqual(getattr(course_run, field), value, 'Field {} is invalid.'.format(field))

        return course_run

    @responses.activate
    @ddt.data(True, False)
    def test_ingest(self, partner_has_marketing_site):
        """ Verify the method ingests data from the Courses API. """
        api_data = self.mock_api()
        if not partner_has_marketing_site:
            self.partner.marketing_site_url_root = None
            self.partner.save()  # pylint: disable=no-member

        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the CourseRuns were created correctly
        expected_num_course_runs = len(api_data)
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

        for datum in api_data:
            self.assert_course_run_loaded(datum, partner_has_marketing_site)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

    @responses.activate
    def test_ingest_exception_handling(self):
        """ Verify the data loader properly handles exceptions during processing of the data from the API. """
        api_data = self.mock_api()

        with mock.patch.object(self.loader, 'clean_strings', side_effect=Exception):
            with mock.patch(LOGGER_PATH) as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, len(api_data))
                msg = 'An error occurred while updating {0} from {1}'.format(
                    api_data[-1]['id'],
                    self.partner.courses_api_url
                )
                mock_logger.exception.assert_called_with(msg)

    @responses.activate
    def test_ingest_canonical(self):
        """ Verify the method ingests data from the Courses API. """
        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.mock_api([
            mock_data.COURSES_API_BODY_ORIGINAL,
            mock_data.COURSES_API_BODY_SECOND,
            mock_data.COURSES_API_BODY_UPDATED,
        ])
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
        # Verify udpated canonical course used to update course
        self.assertEqual(mock_data.COURSES_API_BODY_UPDATED['name'], course.title)
        # Verify the updated course run updated the original course run
        self.assertEqual(mock_data.COURSES_API_BODY_UPDATED['hidden'], course_run_orig.hidden)

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
class EcommerceApiDataLoaderTests(ApiClientTestMixin, DataLoaderTestMixin, TestCase):
    loader_class = EcommerceApiDataLoader

    @property
    def api_url(self):
        return self.partner.ecommerce_api_url

    def mock_api(self):
        # Create existing seats to be removed by ingest
        audit_run = CourseRunFactory(title_override='audit', key='audit/course/run')
        verified_run = CourseRunFactory(title_override='verified', key='verified/course/run')
        credit_run = CourseRunFactory(title_override='credit', key='credit/course/run')
        no_currency_run = CourseRunFactory(title_override='no currency', key='nocurrency/course/run')

        SeatFactory(course_run=audit_run, type=Seat.PROFESSIONAL)
        SeatFactory(course_run=verified_run, type=Seat.PROFESSIONAL)
        SeatFactory(course_run=credit_run, type=Seat.PROFESSIONAL)
        SeatFactory(course_run=no_currency_run, type=Seat.PROFESSIONAL)

        bodies = mock_data.ECOMMERCE_API_BODIES
        url = self.api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies),
            content_type=JSON
        )
        return bodies

    def assert_seats_loaded(self, body):
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

            seat = course_run.seats.get(type=certificate_type, credit_provider=credit_provider, currency=price_currency)

            self.assertEqual(seat.course_run, course_run)
            self.assertEqual(seat.type, certificate_type)
            self.assertEqual(seat.price, price)
            self.assertEqual(seat.currency.code, price_currency)
            self.assertEqual(seat.credit_provider, credit_provider)
            self.assertEqual(seat.credit_hours, credit_hours)
            self.assertEqual(seat.upgrade_deadline, upgrade_deadline)
            self.assertEqual(seat.sku, sku)

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the E-Commerce API. """
        api_data = self.mock_api()
        loaded_course_run_data = api_data[:-1]
        loaded_seat_data = api_data[:-2]

        self.assertEqual(CourseRun.objects.count(), len(loaded_course_run_data))

        # Verify a seat exists on all courses already
        for course_run in CourseRun.objects.all():
            self.assertEqual(course_run.seats.count(), 1)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        for datum in loaded_seat_data:
            self.assert_seats_loaded(datum)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

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


@ddt.ddt
class ProgramsApiDataLoaderTests(ApiClientTestMixin, DataLoaderTestMixin, TestCase):
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

        self.assertEqual(program.type, ProgramType.objects.get(name='XSeries'))

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
        api_data = self.mock_api()
        self.assertEqual(Program.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(2)

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
        self.assert_api_called(2)

        for program in programs:
            self.assert_program_loaded(program)
            self.assert_program_banner_image_loaded(program)
