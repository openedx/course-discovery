""" Tests for data loaders. """
import datetime
import json
from urllib.parse import parse_qs, urlparse, urljoin

import ddt
import responses
from django.conf import settings
from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.data_loaders import (
    OrganizationsApiDataLoader, CoursesApiDataLoader, AbstractDataLoader, DrupalApiDataLoader
)
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Image, LanguageTag, Organization, Subject
)

ACCESS_TOKEN = 'secret'
COURSES_API_URL = 'https://lms.example.com/api/courses/v1'
ORGANIZATIONS_API_URL = 'https://lms.example.com/api/organizations/v0'
MARKETING_API_URL = 'https://example.com/api/catalog/v2/'
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

    def assert_api_called(self, expected_num_calls, check_auth=True):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        self.assertEqual(len(responses.calls), expected_num_calls)
        if check_auth:
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

        # Verify the CourseRuns were created correctly
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


@override_settings(MARKETING_API_URL=MARKETING_API_URL)
@ddt.ddt
class DrupalApiDataLoaderTests(DataLoaderTestMixin, TestCase):

    EXISTING_COURSE_AND_RUN_DATA = ({
        'course_run_key': 'course-v1:SC+BreadX+3T2015',
        'course_key': 'SC+BreadX',
        'title': 'Bread Baking 101',
        'current_language': 'en-us',
    }, {
        'course_run_key': 'course-v1:TX+T201+3T2015',
        'course_key': 'TX+T201',
        'title': 'Testing 201',
        'current_language': ''
    })

    # A course which exists, but has no associated runs
    EXISTING_COURSE = {
        'course_key': 'PartialX+P102',
        'title': 'A partial course',
    }

    api_url = MARKETING_API_URL
    loader_class = DrupalApiDataLoader

    def setUp(self):
        super(DrupalApiDataLoaderTests, self).setUp()
        for course_dict in self.EXISTING_COURSE_AND_RUN_DATA:
            course = Course.objects.create(key=course_dict['course_key'], title=course_dict['title'])
            CourseRun.objects.create(
                key=course_dict['course_run_key'],
                language=self.loader.get_language_tag(course_dict),
                course=course
            )

        Course.objects.create(key=self.EXISTING_COURSE['course_key'], title=self.EXISTING_COURSE['title'])

    def mock_api(self):
        """Mock out the Drupal API. Returns a list of mocked-out course runs."""
        body = {
            'items': [{
                'title': self.EXISTING_COURSE_AND_RUN_DATA[0]['title'],
                'level': {
                    'title': 'Introductory',
                },
                'course_about_uri': '/course/bread-baking-101',
                'course_id': self.EXISTING_COURSE_AND_RUN_DATA[0]['course_run_key'],
                'subjects': [{
                    'title': 'Bread baking',
                }],
                'current_language': self.EXISTING_COURSE_AND_RUN_DATA[0]['current_language'],
                'subtitle': 'Learn about Bread',
                'description': '<p><b>Bread</b> is a <a href="/wiki/Staple_food" title="Staple food">staple food</a>.',
            }, {
                'title': self.EXISTING_COURSE_AND_RUN_DATA[1]['title'],
                'level': {
                    'title': 'Intermediate',
                },
                'course_about_uri': '/course/testing-201',
                'course_id': self.EXISTING_COURSE_AND_RUN_DATA[1]['course_run_key'],
                'subjects': [{
                    'title': 'testing',
                }],
                'current_language': self.EXISTING_COURSE_AND_RUN_DATA[1]['current_language'],
                'subtitle': 'Testing 201',
                'description': "how to test better",
            }, {  # Create a course which exists in LMS/Otto, but without course runs
                'title': self.EXISTING_COURSE['title'],
                'level': {
                    'title': 'Advanced',
                },
                'course_about_uri': '/course/partial-101',
                'course_id': 'course-v1:{course_key}+run'.format(course_key=self.EXISTING_COURSE['course_key']),
                'subjects': [{
                    'title': 'partially fake',
                }],
                'current_language': 'en-us',
                'subtitle': 'Nope',
                'description': 'what is fake?',
            }, {  # Create a fake course run which doesn't exist in LMS/Otto
                'title': 'A partial course',
                'level': {
                    'title': 'Advanced',
                },
                'course_about_uri': '/course/partial-101',
                'course_id': 'course-v1:fakeX+fake+reallyfake',
                'subjects': [{
                    'title': 'seriously fake',
                }],
                'current_language': 'en-us',
                'subtitle': 'Nope',
                'description': 'what is real?',
            }]
        }

        responses.add(
            responses.GET,
            settings.MARKETING_API_URL + 'courses/',
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

        if course_run.language:
            self.assertEqual(course_run.language.code, body['current_language'])
        else:
            self.assertEqual(body['current_language'], '')

    def assert_course_loaded(self, course, body):
        """Verify that the course has been loaded correctly."""
        self.assertEqual(course.title, body['title'])
        self.assertEqual(course.full_description, self.loader.clean_html(body['description']))
        self.assertEqual(course.short_description, self.loader.clean_html(body['subtitle']))
        self.assertEqual(course.marketing_url, urljoin(settings.MARKETING_URL_ROOT, body['course_about_uri']))
        self.assertEqual(course.level_type.name, body['level']['title'])

        self.assert_subjects_loaded(course, body)

    def assert_subjects_loaded(self, course, body):
        """Verify that subjects have been loaded correctly."""
        course_subjects = course.subjects.all()
        api_subjects = body['subjects']
        self.assertEqual(len(course_subjects), len(api_subjects))
        for api_subject in api_subjects:
            loaded_subject = Subject.objects.get(name=api_subject['title'].title())
            self.assertIn(loaded_subject, course_subjects)

    @responses.activate
    def test_ingest(self):
        """Verify the data loader ingests data from Drupal."""
        data = self.mock_api()
        # The faked course should not be loaded from Drupal
        loaded_data = data[:-2]

        self.loader.ingest()

        # Drupal does not paginate its response or check authorization
        self.assert_api_called(1, check_auth=False)

        # Assert that the fake course was not created
        self.assertEqual(CourseRun.objects.count(), len(loaded_data))
        for datum in loaded_data:
            self.assert_course_run_loaded(datum)

        Course.objects.get(key=self.EXISTING_COURSE['course_key'], title=self.EXISTING_COURSE['title'])

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
        ({'current_language': 'en-us'}, LanguageTag(code='en-us', name='English - United States')),
        ({'current_language': None}, None),
    )
    @ddt.unpack
    def test_get_language_tag(self, body, expected):
        self.assertEqual(self.loader.get_language_tag(body), expected)
