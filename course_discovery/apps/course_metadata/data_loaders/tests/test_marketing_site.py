import json
import math
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import mock
import responses
from django.test import TestCase

from course_discovery.apps.course_metadata.data_loaders.marketing_site import SubjectMarketingSiteDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import Subject

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.marketing_site.logger'


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
            'description': self.loader.clean_html(data['body']['value']),
            'subtitle': self.loader.clean_html(data['field_subject_subtitle']['value']),
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
                'description': self.loader.clean_html(data['body']['value']),
                'subtitle': self.loader.clean_html(data['field_subject_subtitle']['value']),
                'card_image_url': data['field_subject_card_image']['url'],
                'banner_image_url': data['field_xseries_banner_image']['url'],
            }
            slug = data['field_subject_url_slug']

            Subject.objects.create(slug=slug, partner=self.partner, **subject_data)

        self.loader.ingest()

        for datum in api_data:
            self.assert_subject_loaded(datum)
