""" Tests for data loaders. """
import json
from urllib.parse import parse_qs, urlparse

import responses
from django.conf import settings
from django.test import TestCase, override_settings

from course_discovery.apps.course_metadata.data_loaders import OrganizationsApiDataLoader
from course_discovery.apps.course_metadata.models import Organization, Image

ACCESS_TOKEN = 'secret'
ORGANIZATIONS_API_URL = 'https://lms.example.com/api/organizations/v0'
JSON = 'application/json'


@override_settings(ORGANIZATIONS_API_URL=ORGANIZATIONS_API_URL)
class OrganizationsApiDataLoaderTests(TestCase):
    def setUp(self):
        super(OrganizationsApiDataLoaderTests, self).setUp()
        self.loader = OrganizationsApiDataLoader(ORGANIZATIONS_API_URL, ACCESS_TOKEN)

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        self.assertEqual(self.loader.api_url, ORGANIZATIONS_API_URL)
        self.assertEqual(self.loader.access_token, ACCESS_TOKEN)

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

        url = '{host}/organizations/'.format(host=settings.ORGANIZATIONS_API_URL)
        responses.add_callback(responses.GET, url, callback=organizations_api_callback(url, bodies), content_type=JSON)

        return bodies

    def assert_organization_loaded(self, body):
        """ Assert an Organization corresponding to the specified data body was properly loaded into the database. """
        organization = Organization.objects.get(key=body['short_name'].strip())
        self.assertEqual(organization.name, body['name'].strip() or None)
        self.assertEqual(organization.description, body['description'].strip() or None)

        image = None
        image_url = body['logo'].strip() or None
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
        self.assertEqual(len(responses.calls), len(data))
        self.assertEqual(responses.calls[0].request.headers['Authorization'], 'Bearer {}'.format(ACCESS_TOKEN))

        # Verify the Organizations were created correctly
        self.assertEqual(Organization.objects.count(), len(data))

        for datum in data:
            self.assert_organization_loaded(datum)
