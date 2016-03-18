import json
from urllib.parse import urlparse, parse_qs

import responses
from django.test import TestCase, override_settings

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.exceptions import CourseNotFoundError
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tests.factories import CourseFactory

ACCESS_TOKEN = 'secret'
COURSES_API_URL = 'https://lms.example.com/api/courses/v1'
ECOMMERCE_API_URL = 'https://ecommerce.example.com/api/v2'
JSON = 'application/json'


@override_settings(ECOMMERCE_API_URL=ECOMMERCE_API_URL, COURSES_API_URL=COURSES_API_URL)
class CourseTests(ElasticsearchTestMixin, TestCase):
    def assert_course_attrs(self, course, attrs):
        """
        Validate the attributes of a given Course.

        Args:
            course (Course)
            attrs (dict)
        """
        for attr, value in attrs.items():
            self.assertEqual(getattr(course, attr), value)

    @responses.activate
    def mock_refresh_all(self):
        """
        Mock the external APIs and refresh all course data.

        Returns:
            [dict]: List of dictionaries representing course content bodies.
        """

        course_bodies = [
            {
                'id': 'a/b/c',
                'url': 'https://ecommerce.example.com/api/v2/courses/a/b/c/',
                'name': 'aaaaa',
                'verification_deadline': '2022-01-01T01:00:00Z',
                'type': 'verified',
                'last_edited': '2015-08-19T15:47:24Z'
            },
            {
                'id': 'aaa/bbb/ccc',
                'url': 'https://ecommerce.example.com/api/v2/courses/aaa/bbb/ccc/',
                'name': 'Introduction to Biology - The Secret of Life',
                'verification_deadline': None,
                'type': 'audit',
                'last_edited': '2015-08-06T19:11:19Z'
            }
        ]

        def ecommerce_api_callback(url, data):
            def request_callback(request):
                # pylint: disable=redefined-builtin
                next = None
                count = len(course_bodies)

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

        def courses_api_callback(url, data):
            def request_callback(request):
                # pylint: disable=redefined-builtin
                next = None
                count = len(course_bodies)

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
                        'previous': None,
                    },
                    'results': [data[page - 1]]
                }

                return 200, {}, json.dumps(body)

            return request_callback

        url = '{host}/courses/'.format(host=ECOMMERCE_API_URL)
        responses.add_callback(responses.GET, url, callback=ecommerce_api_callback(url, course_bodies),
                               content_type=JSON)
        url = '{host}/courses/'.format(host=COURSES_API_URL)
        responses.add_callback(responses.GET, url, callback=courses_api_callback(url, course_bodies), content_type=JSON)

        # Refresh all course data
        Course.refresh_all(ACCESS_TOKEN)
        self.refresh_index()

        return course_bodies

    def test_init(self):
        """ Verify the constructor requires a non-empty string for the ID. """
        msg = 'Course ID cannot be empty or None.'

        with self.assertRaisesRegex(ValueError, msg):
            Course(None)

        with self.assertRaisesRegex(ValueError, msg):
            Course('')

    def test_eq(self):
        """ Verify the __eq__ method returns True if two Course objects have the same `id`. """
        course = CourseFactory()

        # Both objects must be of type Course
        self.assertNotEqual(course, 1)

        # A Course should be equal to itself
        self.assertEqual(course, course)

        # Two Courses are equal if their id attributes match
        self.assertEqual(course, Course(id=course.id, body=course.body))

    def test_str(self):
        """ Verify the __str__ method returns a string representation of the Course. """
        course = CourseFactory()
        expected = 'Course {id}: {name}'.format(id=course.id, name=course.name)
        self.assertEqual(str(course), expected)

    def test_all(self):
        """ Verify the method returns a list of all courses. """
        course_bodies = self.mock_refresh_all()

        courses = []
        for body in course_bodies:
            courses.append(Course.get(body['id']))

        expected = {
            'limit': 10,
            'offset': 0,
            'total': 2,
            'results': courses,
        }

        self.assertDictEqual(Course.all(), expected)

    def test_all_with_limit_and_offset(self):
        """ Verify the method supports limit-offset pagination. """
        limit = 1
        courses = [CourseFactory(id='1'), CourseFactory(id='2')]
        self.refresh_index()

        for offset, course in enumerate(courses):
            expected = {
                'limit': limit,
                'offset': offset,
                'total': len(courses),
                'results': [course],
            }
            self.assertDictEqual(Course.all(limit=limit, offset=offset), expected)

    def test_get(self):
        """ Verify the method returns a single course. """
        course = CourseFactory()
        retrieved = Course.get(course.id)
        self.assertEqual(course, retrieved)

    def test_get_with_missing_course(self):
        """
        Verify the method raises a CourseNotFoundError if the specified course does not exist in the data store.
        """
        # Note (CCB): This consistently fails on Travis with the error below. Trying index refresh as a last-ditch
        # effort to resolve.
        #
        # elasticsearch.exceptions.TransportError: TransportError(503,
        # 'NoShardAvailableActionException[[course_discovery_test][1] null]; nested:
        # IllegalIndexShardStateException[[course_discovery_test][1] CurrentState[POST_RECOVERY] operations only
        # allowed when started/relocated]; ')
        #
        self.refresh_index()
        course_id = 'fake.course'
        expected_msg_regexp = r'Course \[{}\] was not found in the data store.'.format(course_id)
        with self.assertRaisesRegex(CourseNotFoundError, expected_msg_regexp):
            Course.get(course_id)

    def test_search(self):
        """ Verify the method returns query results from the data store. """
        prefix = 'test'
        query = {
            'query': {
                'bool': {
                    'must': [
                        {
                            'wildcard': {
                                'course.name': prefix + '*'
                            }
                        }
                    ]
                }
            }
        }
        courses = []
        for i in range(3):
            courses.append(CourseFactory.create(name=prefix + str(i)))
            CourseFactory.create()

        courses.sort(key=lambda course: course.id.lower())
        self.refresh_index()

        expected = {
            'limit': 10,
            'offset': 0,
            'total': len(courses),
            'results': courses,
        }
        self.assertEqual(Course.search(query), expected)

    @responses.activate
    def test_refresh(self):
        """ Verify the method refreshes data for a single course. """
        course_id = 'SesameStreetX/Cookies/1T2016'
        name = 'C is for Cookie'
        body = {
            'id': course_id,
            'name': name
        }

        # Mock the call to the E-Commerce API
        url = '{host}/courses/{course_id}/'.format(host=ECOMMERCE_API_URL, course_id=course_id)
        responses.add(responses.GET, url, body=json.dumps(body), content_type=JSON)

        # Refresh the course, and ensure the attributes are correct.
        course = Course.refresh(course_id, ACCESS_TOKEN)
        attrs = {
            'id': course_id,
            'body': body,
            'name': name,
        }
        self.assert_course_attrs(course, attrs)

        # Ensure the data is persisted to the data store
        course = Course.get(course_id)
        self.assert_course_attrs(course, attrs)

    def test_refresh_all(self):
        """ Verify the method refreshes data for all courses. """
        course_bodies = self.mock_refresh_all()
        self.refresh_index()

        # Ensure the data is persisted to the data store
        for body in course_bodies:
            course_id = body['id']
            attrs = {
                'id': course_id,
                'body': body,
                'name': body['name'],
            }
            course = Course.get(course_id)
            self.assert_course_attrs(course, attrs)

    def test_name(self):
        """ Verify the method returns the course name. """
        name = 'ABC Course'
        course = Course('a/b/c', {'name': name})
        self.assertEqual(course.name, name)

    def test_save(self):
        """ Verify the method creates and/or updates new courses. """
        course_id = 'TestX/Saving/4T2015'
        body = {
            'id': course_id,
            'name': 'Save Me!'
        }

        self.assertFalse(self.es.exists(index=self.index, doc_type=Course.doc_type, id=course_id))
        Course(course_id, body).save()
        self.refresh_index()

        self.assertTrue(self.es.exists(index=self.index, doc_type=Course.doc_type, id=course_id))
        course = Course.get(course_id)
        self.assertEqual(course.id, course_id)
        self.assertEqual(course.body, body)
