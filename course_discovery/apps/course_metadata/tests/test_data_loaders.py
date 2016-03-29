""" Tests for data loaders. """
import datetime
import json
from urllib.parse import parse_qs, urlparse

import ddt
import responses
from django.conf import settings
from django.test import TestCase, override_settings

from course_discovery.apps.course_metadata.data_loaders import OrganizationsApiDataLoader, CoursesApiDataLoader, \
    AbstractDataLoader
from course_discovery.apps.course_metadata.models import Organization, Image, Course, CourseRun

ACCESS_TOKEN = 'secret'
COURSES_API_URL = 'https://lms.example.com/api/courses/v1'
ORGANIZATIONS_API_URL = 'https://lms.example.com/api/organizations/v0'
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


class DataLoaderTestMixin(object):
    api_url = None
    loader_class = None

    def setUp(self):
        super(DataLoaderTestMixin, self).setUp()
        self.loader = self.loader_class(self.api_url, ACCESS_TOKEN)  # pylint: disable=not-callable

    def assert_api_called(self, expected_num_calls):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        self.assertEqual(len(responses.calls), expected_num_calls)
        self.assertEqual(responses.calls[0].request.headers['Authorization'], 'Bearer {}'.format(ACCESS_TOKEN))

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        self.assertEqual(self.loader.api_url, self.api_url)
        self.assertEqual(self.loader.access_token, ACCESS_TOKEN)


@override_settings(ORGANIZATIONS_API_URL=ORGANIZATIONS_API_URL)
class OrganizationsApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    api_url = ORGANIZATIONS_API_URL
    loader_class = OrganizationsApiDataLoader

    def mock_api(self):
        bodies = [
            {
                'name': 'edX',
                'short_name': ' edX ',
                'description': 'edX',
                'logo': 'https://example.com/edx.jpg',
            },
            {
                'name': 'Massachusetts Institute of Technology ',
                'short_name': 'MITx',
                'description': ' ',
                'logo': '',
            }
        ]

        def organizations_api_callback(url, data):
            def request_callback(request):
                # pylint: disable=redefined-builtin
                next = None
                count = len(bodies)

                # Use the querystring to determine which page should be returned. Default to page 1.
                # Note that the values of the dict returned by `parse_qs` are lists, hence the `[1]` default value.
                qs = parse_qs(urlparse(request.path_url).query)
                page = int(qs.get('page', [1])[0])

                if page < count:
                    next = '{}?page={}'.format(url, page)

                body = {
                    'count': count,
                    'next': next,
                    'previous': None,
                    'results': [data[page - 1]]
                }

                return 200, {}, json.dumps(body)

            return request_callback

        url = '{host}/organizations/'.format(host=self.api_url)
        responses.add_callback(responses.GET, url, callback=organizations_api_callback(url, bodies), content_type=JSON)

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
        data = self.mock_api()
        self.assertEqual(Organization.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        expected_num_orgs = len(data)
        self.assert_api_called(expected_num_orgs)

        # Verify the Organizations were created correctly
        self.assertEqual(Organization.objects.count(), expected_num_orgs)

        for datum in data:
            self.assert_organization_loaded(datum)


@ddt.ddt
@override_settings(COURSES_API_URL=COURSES_API_URL)
class CoursesApiDataLoaderTests(DataLoaderTestMixin, TestCase):
    api_url = COURSES_API_URL
    loader_class = CoursesApiDataLoader

    def mock_api(self):
        bodies = [
            {
                'end': '2015-08-08T00:00:00Z',
                'enrollment_start': '2015-05-15T13:00:00Z',
                'enrollment_end': '2015-06-29T13:00:00Z',
                'id': 'course-v1:MITx+0.111x+2T2015',
                'media': {
                    'image': {
                        'raw': 'http://example.com/image.jpg',
                    },
                },
                'name': 'Making Science and Engineering Pictures: A Practical Guide to Presenting Your Work',
                'number': '0.111x',
                'org': 'MITx',
                'short_description': '',
                'start': '2015-06-15T13:00:00Z',
                'pacing': 'self',
            },
            {
                'effort': None,
                'end': '2015-12-11T06:00:00Z',
                'enrollment_start': None,
                'enrollment_end': None,
                'id': 'course-v1:KyotoUx+000x+2T2016',
                'media': {
                    'course_image': {
                        'uri': '/asset-v1:KyotoUx+000x+2T2016+type@asset+block@000x-course_imagec-378x225.jpg'
                    },
                    'course_video': {
                        'uri': None
                    }
                },
                'name': 'Evolution of the Human Sociality: A Quest for the Origin of Our Social Behavior',
                'number': '000x',
                'org': 'KyotoUx',
                'short_description': '',
                'start': '2015-10-29T09:00:00Z',
                'pacing': 'instructor,'
            },
            {
                # Add a second run of KyotoUx+000x (3T2016) to test merging data across
                # multiple course runs into a single course.
                'effort': None,
                'end': None,
                'enrollment_start': None,
                'enrollment_end': None,
                'id': 'course-v1:KyotoUx+000x+3T2016',
                'media': {
                    'course_image': {
                        'uri': '/asset-v1:KyotoUx+000x+3T2016+type@asset+block@000x-course_imagec-378x225.jpg'
                    },
                    'course_video': {
                        'uri': None
                    }
                },
                'name': 'Evolution of the Human Sociality: A Quest for the Origin of Our Social Behavior',
                'number': '000x',
                'org': 'KyotoUx',
                'short_description': '',
                'start': None,
            },
        ]

        def courses_api_callback(url, data):
            def request_callback(request):
                # pylint: disable=redefined-builtin
                next = None
                count = len(bodies)

                # Use the querystring to determine which page should be returned. Default to page 1.
                # Note that the values of the dict returned by `parse_qs` are lists, hence the `[1]` default value.
                qs = parse_qs(urlparse(request.path_url).query)
                page = int(qs.get('page', [1])[0])

                if page < count:
                    next = '{}?page={}'.format(url, page)

                body = {
                    'pagination': {
                        'count': count,
                        'next': next,
                        'num_pages': len(data),
                        'previous': None,
                    },
                    'results': [data[page - 1]]
                }

                return 200, {}, json.dumps(body)

            return request_callback

        url = '{host}/courses/'.format(host=settings.COURSES_API_URL)
        responses.add_callback(responses.GET, url, callback=courses_api_callback(url, bodies), content_type=JSON)

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
        data = self.mock_api()
        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        expected_num_course_runs = len(data)
        self.assert_api_called(expected_num_course_runs)

        # Verify the Organizations were created correctly
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

        for datum in data:
            self.assert_course_run_loaded(datum)

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
