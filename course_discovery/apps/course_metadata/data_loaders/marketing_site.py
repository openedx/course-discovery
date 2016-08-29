import abc
import logging
from urllib.parse import urlencode
from uuid import UUID

import requests
from django.db.models import Q
from django.utils.functional import cached_property
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, Organization, Person, Subject, Program, Position, LevelType, CourseRun
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag

logger = logging.getLogger(__name__)


class AbstractMarketingSiteDataLoader(AbstractDataLoader):
    PUBLISHED_STATUS_CODE = "1"
    UNPUBLISHED_STATUS_CODE = "0"

    def __init__(self, partner, api_url, access_token=None, token_type=None):
        super(AbstractMarketingSiteDataLoader, self).__init__(partner, api_url, access_token, token_type)

        if not (self.partner.marketing_site_api_username and self.partner.marketing_site_api_password):
            msg = 'Marketing Site API credentials are not properly configured for Partner [{partner}]!'.format(
                partner=partner.short_code)
            raise Exception(msg)

    @cached_property
    def api_client(self):
        username = self.partner.marketing_site_api_username

        # Login by posting to the login form
        login_data = {
            'name': username,
            'pass': self.partner.marketing_site_api_password,
            'form_id': 'user_login',
            'op': 'Log in',
        }

        session = requests.Session()
        login_url = '{root}/user'.format(root=self.api_url)
        response = session.post(login_url, data=login_data)
        expected_url = '{root}/users/{username}'.format(root=self.api_url, username=username)
        if not (response.status_code == 200 and response.url == expected_url):
            raise Exception('Login failed!')

        return session

    def get_query_kwargs(self):
        return {
            'type': self.node_type,
            'max-depth': 2,
            'load-entity-refs': 'file',
        }

    def ingest(self):
        """ Load data for all supported objects (e.g. courses, runs). """
        page = 0
        query_kwargs = self.get_query_kwargs()

        while page is not None and page >= 0:  # pragma: no cover
            kwargs = {
                'page': page,
            }
            kwargs.update(query_kwargs)

            qs = urlencode(kwargs)
            url = '{root}/node.json?{qs}'.format(root=self.api_url, qs=qs)
            response = self.api_client.get(url)

            status_code = response.status_code
            if status_code is not 200:
                msg = 'Failed to retrieve data from {url}\nStatus Code: {status}\nBody: {body}'.format(
                    url=url, status=status_code, body=response.content)
                logger.error(msg)
                raise Exception(msg)

            data = response.json()

            for datum in data['list']:
                try:
                    url = datum['url']
                    datum = self.clean_strings(datum)
                    self.process_node(datum)
                except:  # pylint: disable=bare-except
                    logger.exception('Failed to load %s.', url)

            if 'next' in data:
                page += 1
            else:
                break

    def _get_nested_url(self, field):
        """ Helper method that retrieves the nested `url` field in the specified field, if it exists.
        This works around the fact that Drupal represents empty objects as arrays instead of objects."""
        field = field or {}
        return field.get('url')

    def _get_published(data):
        return data['status'] == self.PUBLISHED_STATUS_CODE

    @abc.abstractmethod
    def process_node(self, data):  # pragma: no cover
        pass

    @abc.abstractproperty
    def node_type(self):  # pragma: no cover
        pass


class XSeriesMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'xseries'

    def process_node(self, data):
        marketing_slug = data['url'].split('/')[-1]
        published = self._get_published(data)

        try:
            program = Program.objects.get(marketing_slug=marketing_slug, partner=self.partner)
        except Program.DoesNotExist:
            if published:
                logger.error(
                    'Program [%s] exists on the marketing site, but not in the Programs Service!', marketing_slug
                )
            return None

        if not published:
            logger.info(
                'Program [%s] unpublished on marketing site.  Deleting!', marketing_slug
            )
            program.delete()

        card_image_url = self._get_nested_url(data.get('field_card_image'))
        video_url = self._get_nested_url(data.get('field_product_video'))

        # NOTE (CCB): Remove the heading at the beginning of the overview. Why this isn't part of the template
        # is beyond me. It's just silly.
        overview = self.clean_html(data['body']['value'])
        overview = overview.lstrip('### XSeries Program Overview').strip()

        data = {
            'subtitle': data.get('field_xseries_subtitle_short'),
            'card_image_url': card_image_url,
            'overview': overview,
            'video': self.get_or_create_video(video_url),
            'credit_redemption_overview': data.get('field_cards_section_description')
        }

        for field, value in data.items():
            setattr(program, field, value)

        program.save()
        logger.info('Processed XSeries with marketing_slug [%s].', marketing_slug)
        return program


class SubjectMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'subject'

    def process_node(self, data):
        slug = data['field_subject_url_slug']
        defaults = {
            'uuid': data['uuid'],
            'name': data['title'],
            'description': self.clean_html(data['body']['value']),
            'subtitle': self.clean_html(data['field_subject_subtitle']['value']),
            'card_image_url': self._get_nested_url(data.get('field_subject_card_image')),
            # NOTE (CCB): This is not a typo. Yes, the banner image for subjects is in a field with xseries in the name.
            'banner_image_url': self._get_nested_url(data.get('field_xseries_banner_image'))

        }
        subject, __ = Subject.objects.update_or_create(slug=slug, partner=self.partner, defaults=defaults)
        logger.info('Processed subject with slug [%s].', slug)
        return subject


class SchoolMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'school'

    def process_node(self, data):
        key = data['title']
        defaults = {
            'uuid': data['uuid'],
            'name': data['field_school_name'],
            'description': self.clean_html(data['field_school_description']['value']),
            'logo_image_url': self._get_nested_url(data.get('field_school_image_logo')),
            'banner_image_url': self._get_nested_url(data.get('field_school_image_banner')),
            'marketing_url_path': 'school/' + data['field_school_url_slug'],
        }
        school, __ = Organization.objects.update_or_create(key=key, partner=self.partner, defaults=defaults)

        self.set_tags(school, data)

        logger.info('Processed school with key [%s].', key)
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


class PersonMarketingSiteDataLoader(AbstractMarketingSiteDataLoader):
    @property
    def node_type(self):
        return 'person'

    def get_query_kwargs(self):
        kwargs = super(PersonMarketingSiteDataLoader, self).get_query_kwargs()
        # NOTE (CCB): We need to include the nested field_collection_item data since that is where
        # the positions are stored.
        kwargs['load-entity-refs'] = 'file,field_collection_item'
        return kwargs

    def process_node(self, data):
        uuid = UUID(data['uuid'])
        slug = data['url'].split('/')[-1]
        defaults = {
            'given_name': data['field_person_first_middle_name'],
            'family_name': data['field_person_last_name'],
            'bio': self.clean_html(data['field_person_resume']['value']),
            'profile_image_url': self._get_nested_url(data.get('field_person_image')),
            'slug': slug,
        }
        person, created = Person.objects.update_or_create(uuid=uuid, partner=self.partner, defaults=defaults)

        # NOTE (CCB): The AutoSlug field kicks in at creation time. We need to apply overrides in a separate
        # operation.
        if created:
            person.slug = slug
            person.save()

        self.set_position(person, data)

        logger.info('Processed person with UUID [%s].', uuid)
        return person

    def set_position(self, person, data):
        uuid = data['uuid']

        try:
            data = data.get('field_person_positions', [])

            if data:
                data = data[0]
                # NOTE (CCB): This is not a typo. The field is misspelled on the marketing site.
                titles = data['field_person_position_tiltes']

                if titles:
                    title = titles[0]

                    # NOTE (CCB): Not all positions are associated with organizations.
                    organization = None
                    organization_name = (data.get('field_person_position_org_link', {}) or {}).get('title')

                    if organization_name:
                        organization = Organization.objects.filter(
                            Q(name__iexact=organization_name) | Q(key__iexact=organization_name) & Q(
                                partner=self.partner)).first()

                    defaults = {
                        'title': title,
                        'organization': None,
                        'organization_override': None,
                    }

                    if organization:
                        defaults['organization'] = organization
                    else:
                        defaults['organization_override'] = organization_name

                    Position.objects.update_or_create(person=person, defaults=defaults)
        except:  # pylint: disable=bare-except
            logger.exception('Failed to set position for person with UUID [%s]!', uuid)


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
        course_run_key_string = data['field_course_id']
        course_run_key = CourseKey.from_string(course_run_key_string)
        key = self.get_course_key_from_course_run_key(course_run_key)
        published = self._get_published(data)

        defaults = {
            'key': key,
            'title': data['field_course_course_title']['value'],
            'number': data['field_course_code'],
            'full_description': self.get_description(data),
            'video': self.get_video(data),
            'short_description': self.clean_html(data['field_course_sub_title_short']),
            'level_type': self.get_level_type(data['field_course_level']),
            'card_image_url': self._get_nested_url(data.get('field_course_image_promoted')),
        }

        if published:
            course, __ = Course.objects.update_or_create(key__iexact=key, partner=self.partner, defaults=defaults)

            self.set_subjects(course, data)
            self.set_authoring_organizations(course, data)
            self.create_course_run(course, data)

            logger.info('Processed course with key [%s].', key)
            return course
        else:
            self.remove_course_run(course_run_key_string)

    def get_description(self, data):
        description = (data.get('field_course_body', {}) or {}).get('value')
        description = description or (data.get('field_course_description', {}) or {}).get('value')
        description = description or ''
        description = self.clean_html(description)
        return description

    def get_level_type(self, name):
        level_type = None

        if name:
            level_type, __ = LevelType.objects.get_or_create(name=name)

        return level_type

    def get_video(self, data):
        video_url = self._get_nested_url(data.get('field_product_video'))
        image_url = self._get_nested_url(data.get('field_course_image_featured_card'))
        return self.get_or_create_video(video_url, image_url)

    def create_course_run(self, course, data):
        uuid = data['uuid']
        key = data['field_course_id']
        slug = data['url'].split('/')[-1]
        language_tags = self._extract_language_tags(data['field_course_languages'])
        language = language_tags[0] if language_tags else None

        defaults = {
            'key': key,
            'course': course,
            'uuid': uuid,
            'language': language,
            'slug': slug,
            'card_image_url': self._get_nested_url(data.get('field_course_image_promoted')),
        }

        try:
            course_run, __ = CourseRun.objects.update_or_create(key__iexact=key, defaults=defaults)
        except TypeError:
            # TODO Fix the data in Drupal (ECOM-5304)
            logger.error('Multiple course runs are identified by the key [%s] or UUID [%s].', key, uuid)
            return None

        self.set_course_run_staff(course_run, data)
        self.set_course_run_transcript_languages(course_run, data)

        logger.info('Processed course run with UUID [%s].', uuid)
        return course_run

    def remove_course_run(self, key):
        try:
            course_run = CourseRun.objects.get(key__iexact=key)
            course_run.delete()
        except CourseRun.DoesNotExist:
            pass

    def _get_objects_by_uuid(self, object_type, raw_objects_data):
        uuids = [_object.get('uuid') for _object in raw_objects_data]
        return object_type.objects.filter(uuid__in=uuids)

    def _extract_language_tags(self, raw_objects_data):
        language_names = [_object['name'].strip() for _object in raw_objects_data]
        return self.get_language_tags_from_names(language_names)

    def set_authoring_organizations(self, course, data):
        schools = self._get_objects_by_uuid(Organization, data['field_course_school_node'])
        course.authoring_organizations.clear()
        course.authoring_organizations.add(*schools)

    def set_subjects(self, course, data):
        subjects = self._get_objects_by_uuid(Subject, data['field_course_subject'])
        course.subjects.clear()
        course.subjects.add(*subjects)

    def set_course_run_staff(self, course_run, data):
        staff = self._get_objects_by_uuid(Person, data['field_course_staff'])
        course_run.staff.clear()
        course_run.staff.add(*staff)

    def set_course_run_transcript_languages(self, course_run, data):
        language_tags = self._extract_language_tags(data['field_course_video_locale_lang'])
        course_run.transcript_languages.clear()
        course_run.transcript_languages.add(*language_tags)
