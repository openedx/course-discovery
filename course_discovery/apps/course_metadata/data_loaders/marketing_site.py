import abc
import concurrent.futures
import datetime
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

import pytz
import waffle
from dateutil import rrule
from django.utils.functional import cached_property
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    AdditionalPromoArea, Course, CourseRun, LevelType, Organization, Person, Subject
)
from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class AbstractMarketingSiteDataLoader(AbstractDataLoader):
    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(AbstractMarketingSiteDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )

        if not (self.partner.marketing_site_api_username and self.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=partner.short_code)
            raise Exception(msg)

    @cached_property
    def api_client(self):

        marketing_site_api_client = MarketingSiteAPIClient(
            self.partner.marketing_site_api_username,
            self.partner.marketing_site_api_password,
            self.api_url
        )

        return marketing_site_api_client.api_session

    def get_query_kwargs(self):
        return {
            'type': self.node_type,
            'max-depth': 2,
            'load-entity-refs': 'file',
        }

    def ingest(self):
        """ Load data for all supported objects (e.g. courses, runs). """
        initial_page = 0
        response = self._request(initial_page)
        self._process_response(response)

        data = response.json()
        if 'next' in data:
            # Add one to avoid requesting the first page again and to make sure
            # we get the last page when range() is used below.
            pages = [self._extract_page(url) + 1 for url in (data['first'], data['last'])]
            pagerange = range(*pages)

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                if self.is_threadsafe:  # pragma: no cover
                    for page in pagerange:
                        executor.submit(self._load_data, page)
                else:
                    for future in [executor.submit(self._request, page) for page in pagerange]:
                        response = future.result()
                        self._process_response(response)

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._request(page)
        self._process_response(response)

    def _request(self, page):
        """Make a request to the marketing site."""
        kwargs = {'page': page}
        kwargs.update(self.get_query_kwargs())

        qs = urlencode(kwargs)
        url = '{root}/node.json?{qs}'.format(root=self.api_url, qs=qs)

        return self.api_client.get(url)

    def _check_status_code(self, response):
        """Check the status code on a response from the marketing site."""
        status_code = response.status_code
        if status_code != 200:
            msg = 'Failed to retrieve data from {url}\nStatus Code: {status}\nBody: {body}'.format(
                url=response.url, status=status_code, body=response.content)
            logger.error(msg)
            raise Exception(msg)

    def _extract_page(self, url):
        """Extract page number from a marketing site URL."""
        qs = parse_qs(urlparse(url).query)

        return int(qs['page'][0])

    def _process_response(self, response):
        """Process a response from the marketing site."""
        self._check_status_code(response)

        data = response.json()
        for node in data['list']:
            try:
                url = node['url']
                node = self.clean_strings(node)
                self.process_node(node)
            except:  # pylint: disable=bare-except
                logger.exception('Failed to load %s.', url)

    def _get_nested_url(self, field):
        """ Helper method that retrieves the nested `url` field in the specified field, if it exists.
        This works around the fact that Drupal represents empty objects as arrays instead of objects."""
        field = field or {}
        return field.get('url')

    @abc.abstractmethod
    def process_node(self, data):  # pragma: no cover
        pass

    @abc.abstractproperty
    def node_type(self):  # pragma: no cover
        pass


class SubjectMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'subject'

    def process_node(self, data):
        slug = data['field_subject_url_slug']
        if ('language' not in data) or (data['language'] == 'und'):
            language_code = 'en'
        else:
            language_code = data['language']
        defaults = {
            'uuid': data['uuid'],
            'name': data['title'],
            'description': self.clean_html(data['body']['value']),
            'subtitle': self.clean_html(data['field_subject_subtitle']['value']),
            'card_image_url': self._get_nested_url(data.get('field_subject_card_image')),
            # NOTE (CCB): This is not a typo. Yes, the banner image for subjects is in a field with xseries in the name.
            'banner_image_url': self._get_nested_url(data.get('field_xseries_banner_image'))
        }

        # There is a bug with django-parler when using django's update_or_create() so we manually update or create.
        try:
            subject = Subject.objects.get(slug=slug, partner=self.partner)
            subject.set_current_language(language_code)
            for key, value in defaults.items():
                setattr(subject, key, value)
            subject.save()
        except Subject.DoesNotExist:
            new_values = {'slug': slug, 'partner': self.partner, '_current_language': language_code}
            new_values.update(defaults)
            subject = Subject(**new_values)
            subject.save()

        logger.info('Processed subject with slug [%s].', slug)
        return subject


class SchoolMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'school'

    def process_node(self, data):
        # NOTE: Some titles in Drupal have the form "UC BerkeleyX" however, course keys (for which we use the
        # organization key) cannot contain spaces.
        key = data['title'].replace(' ', '')
        uuid = UUID(data['uuid'])

        defaults = {
            'name': data['field_school_name'],
            'description': self.clean_html(data['field_school_description']['value']),
            'logo_image_url': self._get_nested_url(data.get('field_school_image_logo')),
            'banner_image_url': self._get_nested_url(data.get('field_school_image_banner')),
            'marketing_url_path': 'school/' + data['field_school_url_slug'],
            'partner': self.partner,
        }

        try:
            school = Organization.objects.get(uuid=uuid, partner=self.partner)
            Organization.objects.filter(pk=school.pk).update(**defaults)
            logger.info('Updated school with key [%s].', school.key)
        except Organization.DoesNotExist:
            # NOTE: Some organizations' keys do not match the title. For example, "UC BerkeleyX" courses use
            # BerkeleyX as the key. Those fixes will be made manually after initial import, and we don't want to
            # override them with subsequent imports. Thus, we only set the key when creating a new organization.
            defaults['key'] = key
            defaults['uuid'] = uuid
            school = Organization.objects.create(**defaults)
            logger.info('Created school with key [%s].', school.key)

        self.set_tags(school, data)

        logger.info('Processed school with key [%s].', school.key)
        return school

    def set_tags(self, school, data):
        tags = []
        mapping = {
            'field_school_is_founder': 'founder',
            'field_school_is_charter': 'charter',
            'field_school_is_contributor': 'contributor',
            'field_school_is_partner': 'partner',
        }

        for field, tag in mapping.items():
            if data.get(field, False):
                tags.append(tag)

        school.tags.set(*tags, clear=True)


class SponsorMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'sponsorer'

    def process_node(self, data):
        uuid = data['uuid']
        body = (data['body'] or {}).get('value')

        if body:
            body = self.clean_html(body)

        defaults = {
            'key': data['url'].split('/')[-1],
            'name': data['title'],
            'description': body,
            'logo_image_url': data['field_sponsorer_image']['url'],
        }
        sponsor, __ = Organization.objects.update_or_create(uuid=uuid, partner=self.partner, defaults=defaults)

        logger.info('Processed sponsor with UUID [%s].', uuid)
        return sponsor


class CourseMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    LANGUAGE_MAP = {
        'English': 'en-us',
        '日本語': 'ja',
        '繁體中文': 'zh-Hant',
        'Indonesian': 'id',
        'Italian': 'it-it',
        'Korean': 'ko',
        'Simplified Chinese': 'zh-Hans',
        'Deutsch': 'de-de',
        'Español': 'es-es',
        'Français': 'fr-fr',
        'Nederlands': 'nl-nl',
        'Português': 'pt-pt',
        'Pусский': 'ru',
        'Svenska': 'sv-se',
        'Türkçe': 'tr',
        'العربية': 'ar-sa',
        'हिंदी': 'hi',
        '中文': 'zh-cmn',
    }

    # Drupal provides a taxonomy term uuid for taxonomy terms, which is the structural model for our course tags in
    # Drupal.  We map these term uuids to discovery's primary identifier for tags, which is the tag name itself.
    STAGE_COURSE_TAG_ID_MAP = {
        'c53b2abf-d4bd-429f-a0a5-211aac95487d': 'professional-programs',
        '57dc60cb-e05c-464c-900f-333d60d249d1': 'communications',
        'd109afc2-d590-40ff-8f0f-04f4e89c39a6': 'accounting',
    }
    PROD_COURSE_TAG_ID_MAP = {
        # Computer Science
        '999c2f3c-268e-4b10-b2df-1fbec5136d05': 'python',
        'c5a55483-f2f0-413a-9943-692731b7fc6c': 'computer-programming',
        '87b215aa-fbd7-47c9-b046-20f20575166a': 'java',
        '906cd957-9d92-41e8-aa02-805ef2d44b29': 'cybersecurity',
        '3939d24d-58d5-4c56-8698-fed85e99f3aa': 'web-development',
        '9f7be9df-9cac-43dc-af47-888f58a77753': 'c-programming',
        '23dad84d-4fc8-40e6-8055-89b41119a631': 'app-development',
        '7720bd23-f193-4e3b-b9ff-06e9b13b4912': 'information-technology',
        '929a3eba-161b-4fb7-966a-af0fea56651a': 'linux',
        'fa854fe6-46fa-4aa8-93aa-640464d0ca18': 'blockchain',
        # Data Science
        '5c9b6677-aa25-4748-89a4-3820972edeae': 'r-programming',
        '4dd710f0-4892-46d1-8a70-edc75be8a7a1': 'data-analysis',
        '0f324ca6-a0a0-4f22-a0ed-1359c76f847f': 'excel',
        '03df0b9d-eac5-4f4b-9b79-28d5001291f9': 'machine-learning',
        '196a9089-0f11-49fc-8077-0f82e3522bd4': 'sql',
    }

    @property
    def node_type(self):
        return 'course'

    @classmethod
    def get_language_tags_from_names(cls, names):
        language_codes = [cls.LANGUAGE_MAP.get(name) for name in names]
        return LanguageTag.objects.filter(code__in=language_codes)

    def get_query_kwargs(self):
        kwargs = super(CourseMarketingSiteDataLoader, self).get_query_kwargs()
        # NOTE (CCB): We need to include the nested taxonomy_term data since that is where the
        # language information is stored.
        kwargs['load-entity-refs'] = 'file,taxonomy_term'
        return kwargs

    def process_node(self, data):

        course_run = self.get_course_run(data)

        if not data.get('field_course_uuid'):

            if course_run:
                self.update_course_run(course_run, data)
                if self.get_course_run_status(data) == CourseRunStatus.Published:
                    # Only update the course object with published course about page
                    try:
                        course = self.update_course(course_run.course, data)
                        self.set_subjects(course, data)
                        self.set_authoring_organizations(course, data)
                        logger.info(
                            'Processed course with key [%s] based on the data from courserun [%s]',
                            course.key,
                            course_run.key
                        )
                    except AttributeError:
                        pass
                else:
                    logger.info(
                        'Course_run [%s] is unpublished, so the course [%s] related is not updated.',
                        data['field_course_id'],
                        course_run.course.number
                    )
            else:
                created = False
                # If the page is not generated from discovery service
                # Do shall then attempt to create a course out of it
                try:
                    course, created = self.get_or_create_course(data)
                    course_run = self.create_course_run(course, data)
                except InvalidKeyError:
                    logger.error('Invalid course key [%s].', data['field_course_id'])

                if created:
                    course.canonical_course_run = course_run
                    course.save()
        else:
            logger.info(
                'Course_run [%s] has uuid [%s] already on course about page. No need to ingest',
                data['field_course_id'],
                data['field_course_uuid']
            )

        # Once we've ingested the course and course run, we update the topic tags with any marketing site tags found.
        if waffle.switch_is_active('migrate_drupal_tags') and course_run:
            self.set_topic_tags(course_run.course, data)

    def get_course_run(self, data):
        course_run_key = data['field_course_id']
        try:
            return CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            return None

    def update_course_run(self, course_run, data):
        validated_data = self.format_course_run_data(data, course_run.course)
        self._update_instance(course_run, validated_data, suppress_publication=True)
        self.set_course_run_staff(course_run, data)
        self.set_course_run_transcript_languages(course_run, data)

        logger.info('Processed course run with UUID [%s].', course_run.uuid)

    def create_course_run(self, course, data):
        defaults = self.format_course_run_data(data, course)

        course_run = CourseRun.objects.create(**defaults)
        self.set_course_run_staff(course_run, data)
        self.set_course_run_transcript_languages(course_run, data)

        return course_run

    def get_or_create_course(self, data):
        defaults = self.format_course_data(data, set_key=True)
        key = defaults['key']

        course, created = Course.objects.get_or_create(key__iexact=key, partner=self.partner, defaults=defaults)

        if created:
            self.set_subjects(course, data)
            self.set_authoring_organizations(course, data)

        return (course, created)

    def update_course(self, course, data):
        validated_data = self.format_course_data(data)
        self._update_instance(course, validated_data)

        return course

    def _update_instance(self, instance, validated_data, **kwargs):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(**kwargs)

    def format_course_run_data(self, data, course):
        uuid = data['uuid']
        key = data['field_course_id']
        language_tags = self._extract_language_tags(data['field_course_languages'])
        language = language_tags[0] if language_tags else None
        start = data.get('field_course_start_date')
        start = datetime.datetime.fromtimestamp(int(start), tz=pytz.UTC) if start else None
        end = data.get('field_course_end_date')
        end = datetime.datetime.fromtimestamp(int(end), tz=pytz.UTC) if end else None
        weeks_to_complete = data.get('field_course_required_weeks')
        min_effort, max_effort = self.get_min_max_effort_per_week(data)

        defaults = {
            'key': key,
            'uuid': uuid,
            'title_override': self.clean_html(data['field_course_course_title']['value']),
            'language': language,
            'card_image_url': self._get_nested_url(data.get('field_course_image_promoted')),
            'status': self.get_course_run_status(data),
            'start': start,
            'pacing_type': self.get_pacing_type(data),
            'hidden': self.get_hidden(data),
            'weeks_to_complete': None,
            'mobile_available': data.get('field_course_enrollment_mobile') or False,
            'video': course.video,
            'course': course,
            # We want to consume the same value for the override here to stay consistent with the marketing site
            'short_description_override': self.clean_html(data['field_course_sub_title_long']['value']) or None,
            'min_effort': min_effort,
            'max_effort': max_effort,
            'outcome': (data.get('field_course_what_u_will_learn', {}) or {}).get('value')
        }

        if weeks_to_complete:
            defaults['weeks_to_complete'] = int(weeks_to_complete)
        elif start and end:
            weeks_to_complete = rrule.rrule(rrule.WEEKLY, dtstart=start, until=end).count()
            defaults['weeks_to_complete'] = int(weeks_to_complete)

        return defaults

    def format_course_data(self, data, set_key=False):
        # Parse key up front to ensure it's a valid key.
        # If the course is so messed up that we can't even parse the key, we don't want it.
        course_run_key = CourseKey.from_string(data['field_course_id'])

        defaults = {
            'title': self.clean_html(data['field_course_course_title']['value']),
            'full_description': self.get_description(data),
            'video': self.get_video(data),
            'short_description': self.clean_html(data['field_course_sub_title_long']['value']),
            'level_type': self.get_level_type(data['field_course_level']),
            'card_image_url': self._get_nested_url(data.get('field_course_image_promoted')),
            'outcome': (data.get('field_course_what_u_will_learn', {}) or {}).get('value'),
            'syllabus_raw': (data.get('field_course_syllabus', {}) or {}).get('value'),
            'prerequisites_raw': (data.get('field_course_prerequisites', {}) or {}).get('value'),
            'extra_description': self.get_extra_description(data)
        }

        if set_key:
            # Only set key/number values if we're asked to, normally we don't want to change these in Discovery
            defaults['key'] = self.get_course_key_from_course_run_key(course_run_key)
            defaults['number'] = data['field_course_code']

        return defaults

    def get_description(self, data):
        description = (data.get('field_course_body', {}) or {}).get('value')
        description = description or (data.get('field_course_description', {}) or {}).get('value')
        description = description or ''
        description = self.clean_html(description)
        return description

    def get_course_run_status(self, data):
        return CourseRunStatus.Published if bool(int(data['status'])) else CourseRunStatus.Unpublished

    def get_level_type(self, name):
        level_type = None

        if name:
            level_type, __ = LevelType.objects.get_or_create(name=name)

        return level_type

    def get_video(self, data):
        video_url = self._get_nested_url(data.get('field_course_video') or data.get('field_product_video'))
        image_url = self._get_nested_url(data.get('field_course_image_featured_card'))
        return self.get_or_create_video(video_url, image_url)

    def get_pacing_type(self, data):
        self_paced = data.get('field_course_self_paced', False)
        return CourseRunPacing.Self if self_paced else CourseRunPacing.Instructor

    def get_hidden(self, data):
        # 'couse' [sic]. The field is misspelled on Drupal. ಠ_ಠ
        hidden = data.get('field_couse_is_hidden', False)
        return hidden is True

    def get_min_max_effort_per_week(self, data):
        """
        Parse effort value from drupal course data which have specific format.
        """
        effort_per_week = data.get('field_course_effort', '')
        min_effort = None
        max_effort = None
        # Ignore effort values in minutes
        if not effort_per_week or 'minutes' in effort_per_week:
            return min_effort, max_effort

        effort_values = [int(keyword) for keyword in re.split(r'\s|-|–|,|\+|~', effort_per_week) if keyword.isdigit()]
        if len(effort_values) == 1:
            max_effort = effort_values[0]
        if len(effort_values) == 2:
            min_effort = effort_values[0]
            max_effort = effort_values[1]

        return min_effort, max_effort

    def _get_objects_by_uuid(self, object_type, raw_objects_data):
        uuids = [_object.get('uuid') for _object in raw_objects_data]
        return object_type.objects.filter(uuid__in=uuids)

    def _extract_language_tags(self, raw_objects_data):
        language_names = [_object['name'].strip() for _object in raw_objects_data]
        return self.get_language_tags_from_names(language_names)

    def get_extra_description(self, raw_objects_data):
        extra_title = raw_objects_data.get('field_course_extra_desc_title', None)
        if extra_title == 'null':
            extra_title = None
        extra_description = (raw_objects_data.get('field_course_extra_description', {}) or {}).get('value')
        if extra_title or extra_description:
            extra, _ = AdditionalPromoArea.objects.get_or_create(
                title=extra_title,
                description=extra_description
            )
            return extra

    def set_topic_tags(self, course, raw_objects_data):
        updated = False

        course_tag_map = self.STAGE_COURSE_TAG_ID_MAP
        if waffle.switch_is_active('production_data_for_tag_migration'):
            course_tag_map = self.PROD_COURSE_TAG_ID_MAP

        for term_object in raw_objects_data.get('field_course_tags'):
            term_uuid = term_object.get('uuid')
            if term_uuid in course_tag_map.keys():
                tag_name = course_tag_map.get(term_uuid)
                if tag_name not in course.topics.names():
                    course.topics.add(tag_name)
                    updated = True

        if updated:
            course.save()
            logger.info('Updated course tags for course [%s].', course.uuid)

    def set_authoring_organizations(self, course, data):
        schools = self._get_objects_by_uuid(Organization, data['field_course_school_node'])
        course.authoring_organizations.clear()
        course.authoring_organizations.add(*schools)

    def set_subjects(self, course, data):
        subjects = self._get_objects_by_uuid(Subject, data['field_course_subject'])
        course.subjects.clear()
        course.subjects.add(*subjects)  # pylint: disable=not-an-iterable

    def set_course_run_staff(self, course_run, data):
        staff = self._get_objects_by_uuid(Person, data['field_course_staff'])
        course_run.staff.clear()
        course_run.staff.add(*staff)

    def set_course_run_transcript_languages(self, course_run, data):
        language_tags = self._extract_language_tags(data['field_course_video_locale_lang'])
        course_run.transcript_languages.clear()
        course_run.transcript_languages.add(*language_tags)
