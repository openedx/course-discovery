import datetime
import json
import math
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import ddt
import mock
import pytz
import responses
from dateutil import rrule
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.marketing_site import (
    CourseMarketingSiteDataLoader, PersonMarketingSiteDataLoader, SchoolMarketingSiteDataLoader,
    SponsorMarketingSiteDataLoader, SubjectMarketingSiteDataLoader
)
from course_discovery.apps.course_metadata.data_loaders.tests import JSON, mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DataLoaderTestMixin
from course_discovery.apps.course_metadata.models import Course, Organization, Person, Subject
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.ietf_language_tags.models import LanguageTag

ENGLISH_LANGUAGE_TAG = LanguageTag(code='en-us', name='English - United States')
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
    def test_ingest(self):
        self.mock_login_response()
        api_data = self.mock_api()

        self.loader.ingest()

        for datum in api_data:
            self.assert_subject_loaded(datum)


class SchoolMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SchoolMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SCHOOL_BODIES

    def assert_school_loaded(self, data):
        key = data['title']
        school = Organization.objects.get(key=key, partner=self.partner)
        expected_values = {
            'uuid': UUID(data['uuid']),
            'name': data['field_school_name'],
            'description': self.loader.clean_html(data['field_school_description']['value']),
            'logo_image_url': data['field_school_image_logo']['url'],
            'banner_image_url': data['field_school_image_banner']['url'],
            'marketing_url_path': 'school/' + data['field_school_url_slug'],
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(school, field), value)

        self.assertEqual(sorted(school.tags.names()), ['charter', 'founder'])

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        schools = self.mock_api()

        self.loader.ingest()

        for school in schools:
            self.assert_school_loaded(school)


class SponsorMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SponsorMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SPONSOR_BODIES

    def assert_sponsor_loaded(self, data):
        uuid = data['uuid']
        school = Organization.objects.get(uuid=uuid, partner=self.partner)

        body = (data['body'] or {}).get('value')

        if body:
            body = self.loader.clean_html(body)

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


class PersonMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = PersonMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_PERSON_BODIES

    def assert_person_loaded(self, data):
        uuid = data['uuid']
        person = Person.objects.get(uuid=uuid, partner=self.partner)
        expected_values = {
            'given_name': data['field_person_first_middle_name'],
            'family_name': data['field_person_last_name'],
            'bio': self.loader.clean_html(data['field_person_resume']['value']),
            'profile_image_url': data['field_person_image']['url'],
            'slug': data['url'].split('/')[-1],
            'profile_url': data['url']
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(person, field), value)

        positions = data['field_person_positions']

        if positions:
            position_data = positions[0]
            titles = position_data['field_person_position_tiltes']

            if titles:
                self.assertEqual(person.position.title, titles[0])
                self.assertEqual(person.position.organization_name,
                                 (position_data.get('field_person_position_org_link') or {}).get('title'))

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        people = self.mock_api()
        factories.OrganizationFactory(name='MIT')

        self.loader.ingest()

        for person in people:
            self.assert_person_loaded(person)


@ddt.ddt
class CourseMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = CourseMarketingSiteDataLoader
    mocked_data = mock_data.UNIQUE_MARKETING_SITE_API_COURSE_BODIES

    def _get_uuids(self, items):
        return [item['uuid'] for item in items]

    def mock_api(self):
        bodies = super().mock_api()

        data_map = {
            factories.SubjectFactory: 'field_course_subject',
            factories.OrganizationFactory: 'field_course_school_node',
            factories.PersonFactory: 'field_course_staff',
        }

        for factory, field in data_map.items():
            uuids = set()

            for body in bodies:
                uuids.update(self._get_uuids(body.get(field, [])))

            for uuid in uuids:
                factory(uuid=uuid, partner=self.partner)

        return bodies

    def test_get_language_tags_from_names(self):
        names = ('English', '中文', None)
        expected = list(LanguageTag.objects.filter(code__in=('en-us', 'zh-cmn')))
        self.assertEqual(list(self.loader.get_language_tags_from_names(names)), expected)

    def test_get_level_type(self):
        self.assertIsNone(self.loader.get_level_type(None))

        name = 'Advanced'
        self.assertEqual(self.loader.get_level_type(name).name, name)

    @ddt.unpack
    @ddt.data(
        ('0', CourseRunStatus.Unpublished),
        ('1', CourseRunStatus.Published),
    )
    def test_get_course_run_status(self, marketing_site_status, expected):
        data = {'status': marketing_site_status}
        self.assertEqual(self.loader.get_course_run_status(data), expected)

    @ddt.data(
        (True, True),
        ('foo', False),
        ('', False),
        (None, False),
    )
    @ddt.unpack
    def test_get_hidden(self, hidden, expected):
        """Verify that the get_hidden method returns the correct Boolean value."""
        data = {'field_couse_is_hidden': hidden}
        self.assertEqual(self.loader.get_hidden(data), expected)

    def test_get_hidden_missing(self):
        """Verify that the get_hidden method can cope with a missing field."""
        self.assertEqual(self.loader.get_hidden({}), False)

    @ddt.data(
        {'field_course_body': {'value': 'Test'}},
        {'field_course_description': {'value': 'Test'}},
        {'field_course_description': {'value': 'Test2'}, 'field_course_body': {'value': 'Test'}},
    )
    def test_get_description(self, data):
        self.assertEqual(self.loader.get_description(data), 'Test')

    def test_get_video(self):
        """Verify that method gets video from any of 'field_course_video' or 'field_product_video.'"""
        image_url = 'https://example.com/image.jpg'
        video_url = 'https://example.com/video.mp4'
        data = {
            'field_course_video': {'url': video_url},
            'field_course_image_featured_card': {'url': image_url}
        }
        video = self.loader.get_video(data)
        self.assertEqual(video.src, video_url)
        self.assertEqual(video.image.src, image_url)

        data = {
            'field_product_video': {'url': video_url},
            'field_course_image_featured_card': {'url': image_url}
        }
        video = self.loader.get_video(data)
        self.assertEqual(video.src, video_url)
        self.assertEqual(video.image.src, image_url)

        self.assertIsNone(self.loader.get_video({}))

    @ddt.unpack
    @ddt.data(
        (True, CourseRunPacing.Self),
        (False, CourseRunPacing.Instructor),
        (None, CourseRunPacing.Instructor),
        ('', CourseRunPacing.Instructor),
    )
    def test_get_pacing_type(self, data_value, expected_pacing_type):
        data = {'field_course_self_paced': data_value}
        self.assertEqual(self.loader.get_pacing_type(data), expected_pacing_type)

    @ddt.data(
        {'field_course_id': ''},
        {'field_course_id': 'EPtestx'},
        {'field_course_id': 'Paradigms-comput'},
        {'field_course_id': 'Bio Course ID'}
    )
    def test_process_node(self, data):
        with LogCapture() as l:
            self.loader.process_node(data)
            l.check(
                (
                    'course_discovery.apps.course_metadata.data_loaders.marketing_site',
                    'ERROR',
                    'Invalid course key [{}].'.format(data['field_course_id'])
                )
            )

    def assert_course_loaded(self, data):
        course = self._get_course(data)

        expected_values = {
            'title': self.loader.clean_html(data['field_course_course_title']['value']),
            'number': data['field_course_code'],
            'full_description': self.loader.get_description(data),
            'video': self.loader.get_video(data),
            'short_description': self.loader.clean_html(data['field_course_sub_title_short']),
            'level_type': self.loader.get_level_type(data['field_course_level']),
            'card_image_url': (data.get('field_course_image_promoted') or {}).get('url'),
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(course, field), value)

        # Verify the subject and authoring organization relationships
        data_map = {
            course.subjects: 'field_course_subject',
            course.authoring_organizations: 'field_course_school_node',
        }

        self.validate_relationships(data, data_map)

    def assert_no_override_unpublished_course_fields(self, data):
        course = self._get_course(data)

        expected_values = {
            'title': data['field_course_course_title']['value'],
            'full_description': self.loader.get_description(data),
            'short_description': self.loader.clean_html(data['field_course_sub_title_short']),
            'card_image_url': (data.get('field_course_image_promoted') or {}).get('url'),
        }

        for field, value in expected_values.items():
            self.assertNotEqual(getattr(course, field), value)

    def validate_relationships(self, data, data_map):
        for relationship, field in data_map.items():
            expected = sorted(self._get_uuids(data.get(field, [])))
            actual = list(relationship.order_by('uuid').values_list('uuid', flat=True))
            actual = [str(item) for item in actual]
            self.assertListEqual(actual, expected, 'Data not properly pulled from {}'.format(field))

    def assert_course_run_loaded(self, data):
        course = self._get_course(data)
        course_run = course.course_runs.get(uuid=data['uuid'])
        language_names = [language['name'] for language in data['field_course_languages']]
        language = self.loader.get_language_tags_from_names(language_names).first()
        start = data.get('field_course_start_date')
        start = datetime.datetime.fromtimestamp(int(start), tz=pytz.UTC) if start else None
        end = data.get('field_course_end_date')
        end = datetime.datetime.fromtimestamp(int(end), tz=pytz.UTC) if end else None
        weeks_to_complete = data.get('field_course_required_weeks')

        expected_values = {
            'key': data['field_course_id'],
            'title_override': self.loader.clean_html(data['field_course_course_title']['value']),
            'language': language,
            'slug': data['url'].split('/')[-1],
            'card_image_url': (data.get('field_course_image_promoted') or {}).get('url'),
            'status': self.loader.get_course_run_status(data),
            'start': start,
            'pacing_type': self.loader.get_pacing_type(data),
            'hidden': self.loader.get_hidden(data),
            'mobile_available': data['field_course_enrollment_mobile'] or False,
            'short_description_override': self.loader.clean_html(data['field_course_sub_title_short']) or None,
        }

        if weeks_to_complete:
            expected_values['weeks_to_complete'] = int(weeks_to_complete)
        elif start and end:
            weeks_to_complete = rrule.rrule(rrule.WEEKLY, dtstart=start, until=end).count()
            expected_values['weeks_to_complete'] = int(weeks_to_complete)

        for field, value in expected_values.items():
            self.assertEqual(getattr(course_run, field), value)

        # Verify the staff relationship
        self.validate_relationships(data, {course_run.staff: 'field_course_staff'})

        language_names = [language['name'] for language in data['field_course_video_locale_lang']]
        expected_transcript_languages = self.loader.get_language_tags_from_names(language_names)
        self.assertEqual(list(course_run.transcript_languages.all()), list(expected_transcript_languages))

        return course_run

    def _get_course(self, data):
        course_run_key = CourseKey.from_string(data['field_course_id'])
        return Course.objects.get(key=self.loader.get_course_key_from_course_run_key(course_run_key),
                                  partner=self.partner)

    @responses.activate
    def test_ingest(self):
        self.mock_login_response()
        data = self.mock_api()

        self.loader.ingest()

        for datum in data:
            self.assert_course_run_loaded(datum)
            self.assert_course_loaded(datum)

    @responses.activate
    def test_canonical(self):
        self.mocked_data = [
            mock_data.ORIGINAL_MARKETING_SITE_API_COURSE_BODY,
            mock_data.NEW_RUN_MARKETING_SITE_API_COURSE_BODY,
            mock_data.UPDATED_MARKETING_SITE_API_COURSE_BODY,
        ]
        self.mock_login_response()
        self.mock_api()

        self.loader.ingest()

        course_run = self.assert_course_run_loaded(mock_data.UPDATED_MARKETING_SITE_API_COURSE_BODY)
        self.assert_course_loaded(mock_data.UPDATED_MARKETING_SITE_API_COURSE_BODY)
        self.assertTrue(course_run.canonical_for_course)

        course_run = self.assert_course_run_loaded(mock_data.NEW_RUN_MARKETING_SITE_API_COURSE_BODY)
        course = course_run.course

        new_run_title = mock_data.NEW_RUN_MARKETING_SITE_API_COURSE_BODY['field_course_course_title']['value']
        self.assertNotEqual(course.title, new_run_title)
        with self.assertRaises(AttributeError):
            course_run.canonical_for_course  # pylint: disable=pointless-statement
