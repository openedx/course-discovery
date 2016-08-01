""" Tests for data loaders. """
import datetime
import json
from decimal import Decimal

import ddt
import mock
import responses
from django.test import TestCase
from edx_rest_api_client.auth import BearerAuth, SuppliedJwtAuth
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey
from pytz import UTC

from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.data_loaders import (
    OrganizationsApiDataLoader, CoursesApiDataLoader, DrupalApiDataLoader, EcommerceApiDataLoader, AbstractDataLoader,
    ProgramsApiDataLoader
)
from course_discovery.apps.course_metadata.models import (
    Course, CourseOrganization, CourseRun, Image, LanguageTag, Organization, Person, Seat, Subject, Program
)
from course_discovery.apps.course_metadata.tests import mock_data
from course_discovery.apps.course_metadata.tests.factories import (
    CourseRunFactory, SeatFactory, ImageFactory, PartnerFactory, PersonFactory, VideoFactory
)

ACCESS_TOKEN = 'secret'
ACCESS_TOKEN_TYPE = 'Bearer'
ENGLISH_LANGUAGE_TAG = LanguageTag(code='en-us', name='English - United States')
JSON = 'application/json'


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
        instances = (ImageFactory(), PersonFactory(), VideoFactory(),)
        AbstractDataLoader.delete_orphans()

        for instance in instances:
            self.assertFalse(instance.__class__.objects.filter(pk=instance.pk).exists())  # pylint: disable=no-member


# pylint: disable=not-callable
@ddt.ddt
class DataLoaderTestMixin(object):
    loader_class = None
    partner = None

    def setUp(self):
        super(DataLoaderTestMixin, self).setUp()
        self.partner = PartnerFactory()
        self.loader = self.loader_class(self.partner, self.api_url, ACCESS_TOKEN, ACCESS_TOKEN_TYPE)

    @property
    def api_url(self):  # pragma: no cover
        raise NotImplementedError

    def assert_api_called(self, expected_num_calls, check_auth=True):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        self.assertEqual(len(responses.calls), expected_num_calls)
        if check_auth:
            self.assertEqual(responses.calls[0].request.headers['Authorization'], 'Bearer {}'.format(ACCESS_TOKEN))

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        self.assertEqual(self.loader.partner.short_code, self.partner.short_code)
        self.assertEqual(self.loader.access_token, ACCESS_TOKEN)
        self.assertEqual(self.loader.token_type, ACCESS_TOKEN_TYPE.lower())

    def test_init_with_unsupported_token_type(self):
        """ Verify the constructor raises an error if an unsupported token type is passed in. """
        with self.assertRaises(ValueError):
            self.loader_class(self.partner, self.api_url, ACCESS_TOKEN, 'not-supported')

    @ddt.unpack
    @ddt.data(
        ('Bearer', BearerAuth),
        ('JWT', SuppliedJwtAuth),
    )
    def test_api_client(self, token_type, expected_auth_class):
        """ Verify the property returns an API client with the correct authentication. """
        loader = self.loader_class(self.partner, self.api_url, ACCESS_TOKEN, token_type)
        client = loader.api_client
        self.assertIsInstance(client, EdxRestApiClient)
        # NOTE (CCB): My initial preference was to mock the constructor and ensure the correct auth arguments
        # were passed. However, that seems nearly impossible. This is the next best alternative. It is brittle, and
        # may break if we ever change the underlying request class of EdxRestApiClient.
        self.assertIsInstance(client._store['session'].auth, expected_auth_class)  # pylint: disable=protected-access


@ddt.ddt
class OrganizationsApiDataLoaderTests(DataLoaderTestMixin, TestCase):
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

    def assert_organization_loaded(self, body):
        """ Assert an Organization corresponding to the specified data body was properly loaded into the database. """
        organization = Organization.objects.get(key=AbstractDataLoader.clean_string(body['short_name']))
        self.assertEqual(organization.name, AbstractDataLoader.clean_string(body['name']))
        self.assertEqual(organization.description, AbstractDataLoader.clean_string(body['description']))

        image = None
        image_url = AbstractDataLoader.clean_string(body['logo'])
        if image_url:
            image = Image.objects.get(src=image_url)

        self.assertEqual(organization.logo_image, image)

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the Organizations API. """
        api_data = self.mock_api()
        self.assertEqual(Organization.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the Organizations were created correctly
        expected_num_orgs = len(api_data)
        self.assertEqual(Organization.objects.count(), expected_num_orgs)

        for datum in api_data:
            self.assert_organization_loaded(datum)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()


@ddt.ddt
class CoursesApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = CoursesApiDataLoader

    @property
    def api_url(self):
        return self.partner.courses_api_url

    def mock_api(self):
        bodies = mock_data.COURSES_API_BODIES
        url = self.api_url + 'courses/'
        responses.add_callback(
            responses.GET,
            url,
            callback=mock_api_callback(url, bodies, pagination=True),
            content_type=JSON
        )
        return bodies

    def assert_course_run_loaded(self, body):
        """ Assert a CourseRun corresponding to the specified data body was properly loaded into the database. """

        # Validate the Course
        course_key = '{org}+{key}'.format(org=body['org'], key=body['number'])
        organization = Organization.objects.get(key=body['org'])
        course = Course.objects.get(key=course_key)

        self.assertEqual(course.title, body['name'])
        self.assertListEqual(list(course.organizations.all()), [organization])

        # Validate the course run
        course_run = CourseRun.objects.get(key=body['id'])
        self.assertEqual(course_run.course, course)
        self.assertEqual(course_run.title, AbstractDataLoader.clean_string(body['name']))
        self.assertEqual(course_run.short_description, AbstractDataLoader.clean_string(body['short_description']))
        self.assertEqual(course_run.start, AbstractDataLoader.parse_date(body['start']))
        self.assertEqual(course_run.end, AbstractDataLoader.parse_date(body['end']))
        self.assertEqual(course_run.enrollment_start, AbstractDataLoader.parse_date(body['enrollment_start']))
        self.assertEqual(course_run.enrollment_end, AbstractDataLoader.parse_date(body['enrollment_end']))
        self.assertEqual(course_run.pacing_type, self.loader.get_pacing_type(body))
        self.assertEqual(course_run.image, self.loader.get_courserun_image(body))
        self.assertEqual(course_run.video, self.loader.get_courserun_video(body))

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the Courses API. """
        api_data = self.mock_api()
        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the CourseRuns were created correctly
        expected_num_course_runs = len(api_data)
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

        for datum in api_data:
            self.assert_course_run_loaded(datum)

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

    @responses.activate
    def test_ingest_exception_handling(self):
        """ Verify the data loader properly handles exceptions during processing of the data from the API. """
        api_data = self.mock_api()

        with mock.patch.object(self.loader, 'clean_strings', side_effect=Exception):
            with mock.patch('course_discovery.apps.course_metadata.data_loaders.logger') as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, len(api_data))
                msg = 'An error occurred while updating {0} from {1}'.format(
                    api_data[-1]['id'],
                    self.partner.courses_api_url
                )
                mock_logger.exception.assert_called_with(msg)

    def test_get_pacing_type_field_missing(self):
        """ Verify the method returns None if the API response does not include a pacing field. """
        self.assertIsNone(self.loader.get_pacing_type({}))

    @ddt.unpack
    @ddt.data(
        ('', None),
        ('foo', None),
        (None, None),
        ('instructor', CourseRun.INSTRUCTOR_PACED),
        ('Instructor', CourseRun.INSTRUCTOR_PACED),
        ('self', CourseRun.SELF_PACED),
        ('Self', CourseRun.SELF_PACED),
    )
    def test_get_pacing_type(self, pacing, expected_pacing_type):
        """ Verify the method returns a pacing type corresponding to the API response's pacing field. """
        self.assertEqual(self.loader.get_pacing_type({'pacing': pacing}), expected_pacing_type)

    @ddt.unpack
    @ddt.data(
        ({}, None),
        ({'image': {}}, None),
        ({'image': {'raw': None}}, None),
        ({'image': {'raw': 'http://example.com/image.jpg'}}, 'http://example.com/image.jpg'),
    )
    def test_get_courserun_image(self, media_body, expected_image_url):
        """ Verify the method returns an Image object with the correct URL. """
        body = {
            'media': media_body
        }
        actual = self.loader.get_courserun_image(body)

        if expected_image_url:
            self.assertEqual(actual.src, expected_image_url)
        else:
            self.assertIsNone(actual)

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
class DrupalApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = DrupalApiDataLoader

    @property
    def api_url(self):
        return self.partner.marketing_site_api_url

    def setUp(self):
        super(DrupalApiDataLoaderTests, self).setUp()
        for course_dict in mock_data.EXISTING_COURSE_AND_RUN_DATA:
            course = Course.objects.create(key=course_dict['course_key'], title=course_dict['title'])
            course_run = CourseRun.objects.create(
                key=course_dict['course_run_key'],
                language=self.loader.get_language_tag(course_dict),
                course=course
            )

            # Add some data that doesn't exist in Drupal already
            person = Person.objects.create(key='orphan_staff_' + course_run.key)
            course_run.staff.add(person)
            organization = Organization.objects.create(key='orphan_org_' + course.key)
            CourseOrganization.objects.create(
                organization=organization,
                course=course,
                relation_type=CourseOrganization.SPONSOR
            )

        Course.objects.create(key=mock_data.EXISTING_COURSE['course_key'], title=mock_data.EXISTING_COURSE['title'])
        Person.objects.create(key=mock_data.ORPHAN_STAFF_KEY)
        Organization.objects.create(key=mock_data.ORPHAN_ORGANIZATION_KEY)

    def mock_api(self):
        """Mock out the Drupal API. Returns a list of mocked-out course runs."""
        body = mock_data.MARKETING_API_BODY
        responses.add(
            responses.GET,
            self.api_url + 'courses/',
            body=json.dumps(body),
            status=200,
            content_type='application/json'
        )
        return body['items']

    def assert_course_run_loaded(self, body):
        """
        Verify that the course run corresponding to `body` has been saved
        correctly.
        """
        course_run_key_str = body['course_id']
        course_run_key = CourseKey.from_string(course_run_key_str)
        course_key = '{org}+{course}'.format(org=course_run_key.org, course=course_run_key.course)
        course = Course.objects.get(key=course_key)
        course_run = CourseRun.objects.get(key=course_run_key_str)

        self.assertEqual(course_run.course, course)

        self.assert_course_loaded(course, body)
        self.assert_staff_loaded(course_run, body)

        if course_run.language:
            self.assertEqual(course_run.language.code, body['current_language'])
        else:
            self.assertEqual(body['current_language'], '')

    def assert_staff_loaded(self, course_run, body):
        """Verify that staff have been loaded correctly."""

        course_run_staff = course_run.staff.all()
        api_staff = body['staff']
        self.assertEqual(len(course_run_staff), len(api_staff))
        for api_staff_member in api_staff:
            loaded_staff_member = Person.objects.get(key=api_staff_member['uuid'])
            self.assertIn(loaded_staff_member, course_run_staff)

    def assert_course_loaded(self, course, body):
        """Verify that the course has been loaded correctly."""
        self.assertEqual(course.title, body['title'])
        self.assertEqual(course.full_description, self.loader.clean_html(body['description']))
        self.assertEqual(course.short_description, self.loader.clean_html(body['subtitle']))
        self.assertEqual(course.level_type.name, body['level']['title'])

        self.assert_subjects_loaded(course, body)
        self.assert_sponsors_loaded(course, body)

    def assert_subjects_loaded(self, course, body):
        """Verify that subjects have been loaded correctly."""
        course_subjects = course.subjects.all()
        api_subjects = body['subjects']
        self.assertEqual(len(course_subjects), len(api_subjects))
        for api_subject in api_subjects:
            loaded_subject = Subject.objects.get(name=api_subject['title'].title())
            self.assertIn(loaded_subject, course_subjects)

    def assert_sponsors_loaded(self, course, body):
        """Verify that sponsors have been loaded correctly."""
        course_sponsors = course.sponsors.all()
        api_sponsors = body['sponsors']
        self.assertEqual(len(course_sponsors), len(api_sponsors))
        for api_sponsor in api_sponsors:
            loaded_sponsor = Organization.objects.get(key=api_sponsor['uuid'])
            self.assertIn(loaded_sponsor, course_sponsors)

    @responses.activate
    def test_ingest(self):
        """Verify the data loader ingests data from Drupal."""
        api_data = self.mock_api()
        # Neither the faked course, nor the empty array, should not be loaded from Drupal.
        # Change this back to -2 as part of ECOM-4493.
        loaded_data = api_data[:-3]

        self.loader.ingest()

        # Drupal does not paginate its response or check authorization
        self.assert_api_called(1, check_auth=False)

        # Assert that the fake course was not created
        self.assertEqual(CourseRun.objects.count(), len(loaded_data))

        for datum in loaded_data:
            self.assert_course_run_loaded(datum)

        Course.objects.get(key=mock_data.EXISTING_COURSE['course_key'], title=mock_data.EXISTING_COURSE['title'])

        # Verify multiple calls to ingest data do NOT result in data integrity errors.
        self.loader.ingest()

        # Verify that orphan data is deleted
        self.assertFalse(Person.objects.filter(key=mock_data.ORPHAN_STAFF_KEY).exists())
        self.assertFalse(Organization.objects.filter(key=mock_data.ORPHAN_ORGANIZATION_KEY).exists())
        self.assertFalse(Person.objects.filter(key__startswith='orphan_staff_').exists())
        self.assertFalse(Organization.objects.filter(key__startswith='orphan_org_').exists())

    @responses.activate
    def test_ingest_exception_handling(self):
        """ Verify the data loader properly handles exceptions during processing of the data from the API. """
        api_data = self.mock_api()
        # Include all data, except the empty array.
        # TODO: Remove the -1 after ECOM-4493 is in production.
        expected_call_count = len(api_data) - 1

        with mock.patch.object(self.loader, 'clean_strings', side_effect=Exception):
            with mock.patch('course_discovery.apps.course_metadata.data_loaders.logger') as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, expected_call_count)

                # TODO: Change the -2 to -1 after ECOM-4493 is in production.
                msg = 'An error occurred while updating {0} from {1}'.format(
                    api_data[-2]['course_id'],
                    self.partner.marketing_site_api_url
                )
                mock_logger.exception.assert_called_with(msg)

    @ddt.data(
        ('', ''),
        ('<h1>foo</h1>', '# foo'),
        ('<a href="http://example.com">link</a>', '[link](http://example.com)'),
        ('<strong>foo</strong>', '**foo**'),
        ('<em>foo</em>', '_foo_'),
        ('\nfoo\n', 'foo'),
        ('<span>foo</span>', 'foo'),
        ('<div>foo</div>', 'foo'),
    )
    @ddt.unpack
    def test_clean_html(self, to_clean, expected):
        self.assertEqual(self.loader.clean_html(to_clean), expected)

    @ddt.data(
        ({'current_language': ''}, None),
        ({'current_language': 'not-real'}, None),
        ({'current_language': 'en-us'}, ENGLISH_LANGUAGE_TAG),
        ({'current_language': 'en'}, ENGLISH_LANGUAGE_TAG),
        ({'current_language': None}, None),
    )
    @ddt.unpack
    def test_get_language_tag(self, body, expected):
        self.assertEqual(self.loader.get_language_tag(body), expected)


@ddt.ddt
class EcommerceApiDataLoaderTests(DataLoaderTestMixin, TestCase):
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
class ProgramsApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    loader_class = ProgramsApiDataLoader

    @property
    def api_url(self):
        return self.partner.programs_api_url

    def mock_api(self):
        bodies = mock_data.PROGRAMS_API_BODIES
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
        program = Program.objects.get(uuid=AbstractDataLoader.clean_string(body['uuid']))

        self.assertEqual(program.title, body['name'])
        for attr in ('subtitle', 'category', 'status', 'marketing_slug',):
            self.assertEqual(getattr(program, attr), AbstractDataLoader.clean_string(body[attr]))

        keys = [org['key'] for org in body['organizations']]
        expected_organizations = list(Organization.objects.filter(key__in=keys))
        self.assertEqual(keys, [org.key for org in expected_organizations])
        self.assertListEqual(list(program.organizations.all()), expected_organizations)

        image_url = body.get('banner_image_urls', {}).get('w435h145')
        if image_url:
            image = Image.objects.get(src=image_url, width=self.loader.image_width,
                                      height=self.loader.image_height)
            self.assertEqual(program.image, image)

    @responses.activate
    def test_ingest(self):
        """ Verify the method ingests data from the Organizations API. """
        api_data = self.mock_api()
        self.assertEqual(Program.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the Programs were created correctly
        expected_num_programs = len(api_data)
        self.assertEqual(Program.objects.count(), expected_num_programs)

        for datum in api_data:
            self.assert_program_loaded(datum)

        self.loader.ingest()
