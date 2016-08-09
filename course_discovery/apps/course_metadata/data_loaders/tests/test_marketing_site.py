import json
from urllib.parse import parse_qs, urlparse

import ddt
import mock
import responses
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    DrupalApiDataLoader, XSeriesMarketingSiteDataLoader,
)
from course_discovery.apps.course_metadata.data_loaders.tests import JSON
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import ApiClientTestMixin, DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import (
    Course, CourseOrganization, CourseRun, Organization, Person, Subject, Program, Video,
)
from course_discovery.apps.course_metadata.tests import mock_data
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag

ENGLISH_LANGUAGE_TAG = LanguageTag(code='en-us', name='English - United States')
LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.marketing_site.logger'


@ddt.ddt
class DrupalApiDataLoaderTests(ApiClientTestMixin, DataLoaderTestMixin, TestCase):
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
            with mock.patch(LOGGER_PATH) as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, expected_call_count)

                # TODO: Change the -2 to -1 after ECOM-4493 is in production.
                msg = 'An error occurred while updating {0} from {1}'.format(
                    api_data[-2]['course_id'],
                    self.partner.marketing_site_api_url
                )
                mock_logger.exception.assert_called_with(msg)

    @ddt.unpack
    @ddt.data(
        ({'image': {}}, None),
        ({'image': 'http://example.com/image.jpg'}, 'http://example.com/image.jpg'),
    )
    def test_get_courserun_image(self, media_body, expected_image_url):
        """ Verify the method returns an Image object with the correct URL. """
        actual = self.loader.get_courserun_image(media_body)

        if expected_image_url:
            self.assertEqual(actual.src, expected_image_url)
        else:
            self.assertIsNone(actual)

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


class AbstractMarketingSiteDataLoaderTestMixin(DataLoaderTestMixin):
    @property
    def api_url(self):
        return self.partner.marketing_site_url_root

    def mock_api_callback(self, url, data):
        """ Paginate the data, one item per page. """

        def request_callback(request):
            count = len(data)

            # Use the querystring to determine which page should be returned. Default to page 1.
            # Note that the values of the dict returned by `parse_qs` are lists, hence the `[1]` default value.
            qs = parse_qs(urlparse(request.path_url).query)
            page = int(qs.get('page', [0])[0])
            page_size = 1

            body = {
                'list': [data[page]]
            }

            if (page * page_size) < count - 1:
                next_page = page + 1
                next_url = '{}?page={}'.format(url, next_page)
                body['next'] = next_url

            return 200, {}, json.dumps(body)

        return request_callback

    def mock_login_response(self, failure=False):
        url = self.api_url + 'user'
        landing_url = '{base}users/{username}'.format(base=self.api_url,
                                                      username=self.partner.marketing_site_api_username)
        status = 500 if failure else 302
        adding_headers = {}

        if not failure:
            adding_headers['Location'] = landing_url
        responses.add(responses.POST, url, status=status, adding_headers=adding_headers)
        responses.add(responses.GET, landing_url)

    def mock_api_failure(self):
        url = self.api_url + 'node.json'
        responses.add(responses.GET, url, status=500)

    @responses.activate
    def test_ingest_with_api_failure(self):
        self.mock_login_response()
        self.mock_api_failure()

        with self.assertRaises(Exception):
            self.loader.ingest()

    @responses.activate
    def test_ingest_exception_handling(self):
        """ Verify the data loader properly handles exceptions during processing of the data from the API. """
        self.mock_login_response()
        api_data = self.mock_api()

        with mock.patch.object(self.loader, 'clean_strings', side_effect=Exception):
            with mock.patch(LOGGER_PATH) as mock_logger:
                self.loader.ingest()
                self.assertEqual(mock_logger.exception.call_count, len(api_data))
                calls = [mock.call('Failed to load %s.', datum['url']) for datum in api_data]
                mock_logger.exception.assert_has_calls(calls)

    @responses.activate
    def test_api_client_login_failure(self):
        self.mock_login_response(failure=True)
        with self.assertRaises(Exception):
            self.loader.api_client  # pylint: disable=pointless-statement

    def test_constructor_without_credentials(self):
        """ Verify the constructor raises an exception if the Partner has no marketing site credentials set. """
        self.partner.marketing_site_api_username = None
        with self.assertRaises(Exception):
            self.loader_class(self.partner, self.api_url)  # pylint: disable=not-callable


class XSeriesMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = XSeriesMarketingSiteDataLoader
    LOGIN_COOKIE = ('session_id', 'abc123')

    def create_mock_programs(self, programs):
        for program in programs:
            marketing_slug = program['url'].split('/')[-1]
            ProgramFactory(marketing_slug=marketing_slug, partner=self.partner)

    def mock_api(self):
        bodies = mock_data.MARKETING_SITE_API_XSERIES_BODIES
        self.create_mock_programs(bodies)
        url = self.api_url + 'node.json'

        responses.add_callback(
            responses.GET,
            url,
            callback=self.mock_api_callback(url, bodies),
            content_type=JSON
        )

        return bodies

    def assert_program_loaded(self, data):
        marketing_slug = data['url'].split('/')[-1]
        program = Program.objects.get(marketing_slug=marketing_slug, partner=self.partner)

        overview = self.loader.clean_html(data['body']['value'])
        overview = overview.lstrip('### XSeries Program Overview').strip()
        self.assertEqual(program.overview, overview)

        self.assertEqual(program.subtitle, data.get('field_xseries_subtitle_short'))

        card_image_url = data.get('field_card_image', {}).get('url')
        self.assertEqual(program.card_image_url, card_image_url)

        video_url = data.get('field_product_video', {}).get('url')
        if video_url:
            video = Video.objects.get(src=video_url)
            self.assertEqual(program.video, video)

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        api_data = self.mock_api()

        self.loader.ingest()

        for datum in api_data:
            self.assert_program_loaded(datum)

    @responses.activate
    def test_ingest_with_missing_programs(self):
        """ Verify ingestion properly logs issues when programs exist on the marketing site,
        but not the Programs API. """
        self.mock_login_response()
        api_data = self.mock_api()

        Program.objects.all().delete()
        self.assertEqual(Program.objects.count(), 0)

        with mock.patch(LOGGER_PATH) as mock_logger:
            self.loader.ingest()
            self.assertEqual(Program.objects.count(), 0)

            calls = [mock.call('Program [%s] exists on the marketing site, but not in the Programs Service!',
                               datum['url'].split('/')[-1]) for datum in api_data]
            mock_logger.error.assert_has_calls(calls)
