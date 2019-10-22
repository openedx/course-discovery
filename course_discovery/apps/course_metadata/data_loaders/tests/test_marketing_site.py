import json
import math
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import mock
import responses
from django.test import TestCase

from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    CourseMarketingSiteDataLoader, SchoolMarketingSiteDataLoader, SponsorMarketingSiteDataLoader,
    SubjectMarketingSiteDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import Course, Organization, Subject
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, PartnerFactory
from course_discovery.apps.course_metadata.utils import clean_html

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.marketing_site.logger'
MOCK_DRUPAL_REDIRECT_CSV_FILE = 'data/mock_redirect_csv.csv'


class AbstractMarketingSiteDataLoaderTestMixin(DataLoaderTestMixin):
    mocked_data = []

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
                'list': [data[page]],
                'first': '{}?page={}'.format(url, 0),
                'last': '{}?page={}'.format(url, math.ceil(count / page_size) - 1),
            }

            if (page * page_size) < count - 1:
                next_page = page + 1
                next_url = '{}?page={}'.format(url, next_page)
                body['next'] = next_url

            return 200, {}, json.dumps(body)

        return request_callback

    def mock_api(self):
        bodies = self.mocked_data
        url = self.api_url + 'node.json'

        responses.add_callback(
            responses.GET,
            url,
            callback=self.mock_api_callback(url, bodies),
            content_type=JSON
        )

        return bodies

    def mock_login_response(self, failure=False):
        url = self.api_url + 'user'
        landing_url = '{base}admin'.format(base=self.api_url)
        status = 500 if failure else 302
        adding_headers = {}

        if not failure:
            adding_headers['Location'] = landing_url
        responses.add(responses.POST, url, status=status, adding_headers=adding_headers)

        responses.add(
            responses.GET,
            landing_url,
            status=(500 if failure else 200)
        )

        responses.add(
            responses.GET,
            '{root}restws/session/token'.format(root=self.api_url),
            body='test token',
            content_type='text/html',
            status=200
        )

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


class SubjectMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SubjectMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SUBJECT_BODIES

    def assert_subject_loaded(self, data):
        slug = data['field_subject_url_slug']
        subject = Subject.objects.get(slug=slug, partner=self.partner)
        expected_values = {
            'uuid': UUID(data['uuid']),
            'name': data['title'],
            'description': clean_html(data['body']['value']),
            'subtitle': clean_html(data['field_subject_subtitle']['value']),
            'card_image_url': data['field_subject_card_image']['url'],
            'banner_image_url': data['field_xseries_banner_image']['url'],
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(subject, field), value)

    @responses.activate
    def test_ingest_create(self):
        self.mock_login_response()
        api_data = self.mock_api()

        self.loader.ingest()

        for datum in api_data:
            self.assert_subject_loaded(datum)

    @responses.activate
    def test_ingest_update(self):
        self.mock_login_response()
        api_data = self.mock_api()
        for data in api_data:
            subject_data = {
                'uuid': UUID(data['uuid']),
                'name': data['title'],
                'description': clean_html(data['body']['value']),
                'subtitle': clean_html(data['field_subject_subtitle']['value']),
                'card_image_url': data['field_subject_card_image']['url'],
                'banner_image_url': data['field_xseries_banner_image']['url'],
            }
            slug = data['field_subject_url_slug']

            Subject.objects.create(slug=slug, partner=self.partner, **subject_data)

        self.loader.ingest()

        for datum in api_data:
            self.assert_subject_loaded(datum)


class SchoolMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SchoolMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SCHOOL_BODIES

    def assert_school_loaded(self, data):
        school = Organization.objects.get(uuid=UUID(data['uuid']), partner=self.partner)
        expected_values = {
            'key': data['title'],
            'name': data['field_school_name'],
            'description': clean_html(data['field_school_description']['value']),
            'logo_image_url': data['field_school_image_logo']['url'],
            'banner_image_url': data['field_school_image_banner']['url'],
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(school, field), value)

        self.assertEqual(sorted(school.tags.names()), ['charter', 'displayed_on_schools_and_partners_page', 'founder'])

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        schools = self.mock_api()

        self.loader.ingest()

        for school in schools:
            self.assert_school_loaded(school)

        # If the key of an organization changes, the data loader should continue updating the
        # organization by matching on the UUID.
        school = Organization.objects.get(key='MITx', partner=self.partner)
        # NOTE (CCB): As an MIT alum, this makes me feel dirty. IHTFT(est)!
        modified_key = 'MassTechX'
        school.key = modified_key
        school.save()

        count = Organization.objects.count()
        self.loader.ingest()
        school.refresh_from_db()

        assert Organization.objects.count() == count
        assert school.key == modified_key


class SponsorMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SponsorMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SPONSOR_BODIES

    def assert_sponsor_loaded(self, data):
        uuid = data['uuid']
        school = Organization.objects.get(uuid=uuid, partner=self.partner)

        body = (data['body'] or {}).get('value')

        if body:
            body = clean_html(body)

        expected_values = {
            'key': data['url'].split('/')[-1],
            'name': data['title'],
            'description': body,
            'logo_image_url': data['field_sponsorer_image']['url'],
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(school, field), value)

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        sponsors = self.mock_api()

        self.loader.ingest()

        for sponsor in sponsors:
            self.assert_sponsor_loaded(sponsor)


class CourseMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = CourseMarketingSiteDataLoader
    mocked_data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES

    @mock.patch('course_discovery.apps.course_metadata.data_loaders.marketing_site.DRUPAL_REDIRECT_CSV_FILE',
                MOCK_DRUPAL_REDIRECT_CSV_FILE)
    def setUp(self):
        super().setUp()

    def get_key_from_mocked_data(self, course_dict):
        compound_key = course_dict['field_course_id'].split('/')
        return '{org}+{course}'.format(org=compound_key[0], course=compound_key[1])

    def setup_courses(self):
        # In our current world, we do not create courses from
        # marketing site data, but we need them for creating redirects.
        partner = PartnerFactory()
        for course in self.mocked_data:
            title = course['field_course_course_title']['value']
            mocked = CourseFactory(key=self.get_key_from_mocked_data(course), partner=partner, title=title)
            mocked.set_active_url_slug('')  # force the active url slug to be the slugified title

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        self.setup_courses()
        self.mock_api()

        original_active_slugs_by_course_key = {}
        for test_course in Course.everything.all():
            original_active_slugs_by_course_key[test_course.key] = test_course.active_url_slug

        self.loader.ingest()

        test_course_1 = Course.everything.get(key='HarvardX+CS50x')
        test_course_2 = Course.everything.get(key='HarvardX+PH207x')
        test_course_3 = Course.everything.get(key='HarvardX+CB22x')

        active_url_slug_1 = test_course_1.active_url_slug
        active_url_slug_2 = test_course_2.active_url_slug
        active_url_slug_3 = test_course_3.active_url_slug

        # active slugs should not be affected
        self.assertEqual(active_url_slug_1, original_active_slugs_by_course_key[test_course_1.key])
        self.assertEqual(active_url_slug_2, original_active_slugs_by_course_key[test_course_2.key])
        self.assertEqual(active_url_slug_3, original_active_slugs_by_course_key[test_course_3.key])

        test_course_1_paths = list(map(lambda x: x.value, test_course_1.url_redirects.all()))

        self.assertIn('/course/long/path', test_course_1_paths)
        self.assertIn('/different-prefix/introduction-to-computer-science', test_course_1_paths)
        self.assertEqual(test_course_1.url_redirects.count(), 2)

        self.assertTrue(test_course_2.url_slug_history.filter(url_slug='health-numbers',
                                                              is_active=False,
                                                              is_active_on_draft=False).exists())
        self.assertEqual(test_course_2.url_redirects.count(), 0)
        self.assertEqual(test_course_3.url_redirects.count(), 0)
