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
from course_discovery.apps.course_metadata.data_loaders.marketing_site import logger as marketing_site_logger
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


class SchoolMarketingSiteDataLoaderTests(AbstractMarketingSiteDataLoaderTestMixin, TestCase):
    loader_class = SchoolMarketingSiteDataLoader
    mocked_data = mock_data.MARKETING_SITE_API_SCHOOL_BODIES

    def assert_school_loaded(self, data):
        school = Organization.objects.get(uuid=UUID(data['uuid']), partner=self.partner)
        expected_values = {
            'key': data['title'],
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
            'published': True if data['status'] == '1' else False,
        }

        for field, value in expected_values.items():
            self.assertEqual(getattr(person, field), value)

    def ingest_mock_data(self):
        self.mock_login_response()
        people = self.mock_api()
        factories.OrganizationFactory(name='MIT')
        for person in people:
            Person.objects.create(uuid=person['uuid'], partner=self.partner)
        self.loader.ingest()
        return people

    @responses.activate
    def test_ingest(self):
        people = self.ingest_mock_data()
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

    def test_get_extra_description(self):
        self.assertIsNone(self.loader.get_extra_description({}))

        extra_description_raw = {
            'field_course_extra_desc_title': 'null',
            'field_course_extra_description': {}
        }

        extra_description = self.loader.get_extra_description(extra_description_raw)
        self.assertIsNone(extra_description)

        title = 'additional'
        description = 'promo'
        extra_description_raw = {
            'field_course_extra_desc_title': title,
            'field_course_extra_description': {
                'value': description
            }
        }
        extra_description = self.loader.get_extra_description(extra_description_raw)
        self.assertEqual(extra_description.title, title)
        self.assertEqual(extra_description.description, description)

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

    @ddt.data(
        (None, None, None),
        ('Browse at your own pace.', None, None),
        ('1.5 - 3.5 hours/week', None, None),
        ('8 hours/week', None, 8),
        ('2.5-5 hours.', None, 5),
        ('5+ hours per week', None, 5),
        ('3 horas por semana', None, 3),
        ('1 - 1.5 hours per week', None, 1),
        ('6 hours of video/300 multiple choice questions', None, 6),
        ('6 to 9 hours/week', 6, 9),
        ('4-6 hours per week', 4, 6),
        ('About 5-12 hrs/week.', 5, 12),
        ('4 - 8 hours/week | 小时／周', 4, 8),
        ('6 horas/semana, 6 hours/week', 6, 6),
        ('Estimated effort: 4–5 hours per week.', 4, 5),
        ('4-6 hours per week depending on the background of the student.', 4, 6),
        ('每周 2-3 小时 | 2-3 hours per week', None, None),
        ('Part 1: 3 hours; Part 2: 4 hours; Part 3: 2 hours', None, None),
        ('From 10 - 60 minutes, or as much time as you want.', None, None),
        ('3-4 hours per unit (recommended pace: 1 unit per week)', None, None),
        ('5-8 hours/week; 2-3 hours for lectures; 3-5 hours for homework/self-study', None, None),
    )
    @ddt.unpack
    def test_get_min_max_effort_per_week(self, course_effort_string, expected_min_effort, expected_max_effort):
        """
        Verify that the method `get_min_max_effort_per_week` correctly parses
        most of the the effort values which have specific format and maps them
        to min effort and max effort values.
        """
        data = {'field_course_effort': course_effort_string}
        min_effort, max_effort = self.loader.get_min_max_effort_per_week(data)
        self.assertEqual(min_effort, expected_min_effort)
        self.assertEqual(max_effort, expected_max_effort)

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
        with LogCapture(marketing_site_logger.name) as lc:
            self.loader.process_node(data)
            lc.check(
                (
                    marketing_site_logger.name,
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
            'short_description': self.loader.clean_html(data['field_course_sub_title_long']['value']),
            'level_type': self.loader.get_level_type(data['field_course_level']),
            'card_image_url': (data.get('field_course_image_promoted') or {}).get('url'),
            'outcome': (data.get('field_course_what_u_will_learn', {}) or {}).get('value'),
            'syllabus_raw': (data.get('field_course_syllabus', {}) or {}).get('value'),
            'prerequisites_raw': (data.get('field_course_prerequisites', {}) or {}).get('value'),
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
            'short_description_override': self.loader.clean_html(data['field_course_sub_title_long']['value']) or None,
            'outcome': (data.get('field_course_what_u_will_learn', {}) or {}).get('value'),
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
    def test_course_run_creation(self):
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

    @responses.activate
    def test_discovery_created_course_run(self):
        self.mocked_data = [
            mock_data.DISCOVERY_CREATED_MARKETING_SITE_API_COURSE_BODY
        ]

        self.mock_login_response()
        self.mock_api()

        with LogCapture(marketing_site_logger.name) as lc:
            self.loader.ingest()
            lc.check(
                (
                    marketing_site_logger.name,
                    'INFO',
                    'Course_run [{}] has uuid [{}] already on course about page. No need to ingest'.format(
                        mock_data.DISCOVERY_CREATED_MARKETING_SITE_API_COURSE_BODY['field_course_id'],
                        mock_data.DISCOVERY_CREATED_MARKETING_SITE_API_COURSE_BODY['field_course_uuid'])
                )
            )

    @responses.activate
    def test_discovery_unpublished_course_run(self):
        self.mocked_data = [
            mock_data.UPDATED_MARKETING_SITE_API_COURSE_BODY,
            mock_data.ORIGINAL_MARKETING_SITE_API_COURSE_BODY
        ]

        self.mock_login_response()
        self.mock_api()

        with LogCapture(marketing_site_logger.name) as lc:
            self.loader.ingest()
            lc.check(
                (
                    marketing_site_logger.name,
                    'INFO',
                    'Processed course run with UUID [{}].'.format(
                        mock_data.UPDATED_MARKETING_SITE_API_COURSE_BODY['uuid'])
                ),
                (
                    marketing_site_logger.name,
                    'INFO',
                    'Course_run [{}] is unpublished, so the course [{}] related is not updated.'.format(
                        mock_data.ORIGINAL_MARKETING_SITE_API_COURSE_BODY['field_course_id'],
                        mock_data.ORIGINAL_MARKETING_SITE_API_COURSE_BODY['field_course_code'])
                )
            )
