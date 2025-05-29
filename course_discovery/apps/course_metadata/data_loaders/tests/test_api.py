import datetime

import ddt
import mock
import responses
from django.test import TestCase

from course_discovery.apps.core.tests.utils import mock_api_callback
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.api import (
    AbstractDataLoader, CoursesApiDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import ApiClientTestMixin, DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Organization
)
from course_discovery.apps.course_metadata.tests.factories import (
    ImageFactory, VideoFactory
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
            self.assertFalse(instance.__class__.objects.filter(pk=instance.pk).exists())

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
            'end': self.loader.parse_date(body['end']),
            'enrollment_start': self.loader.parse_date(body['enrollment_start']),
            'enrollment_end': self.loader.parse_date(body['enrollment_end']),
            'card_image_url': None,
            'title_override': None,
        }

        if not partner_has_marketing_site:
            expected_values.update({
                'start': self.loader.parse_date(body['start']),
                'card_image_url': body['media'].get('image', {}).get('raw'),
                'title_override': body['name'],
                'status': CourseRunStatus.Published,
                'pacing_type': self.loader.get_pacing_type(body),
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
            self.partner.save()

        self.assertEqual(Course.objects.count(), 0)
        self.assertEqual(CourseRun.objects.count(), 0)

        self.loader.ingest()

        # Verify the API was called with the correct authorization header
        self.assert_api_called(1)

        # Verify the CourseRuns were created correctly
        expected_num_course_runs = len(api_data)
        self.assertEqual(CourseRun.objects.count(), expected_num_course_runs)

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
