import abc
import logging
from urllib.parse import urljoin, urlencode

import requests
from django.utils.functional import cached_property

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, CourseOrganization, CourseRun, Image, LanguageTag, LevelType, Organization, Person, Subject, Program,
)

logger = logging.getLogger(__name__)


class DrupalApiDataLoader(AbstractDataLoader):
    """Loads course runs from the Drupal API."""

    def ingest(self):
        api_url = self.partner.marketing_site_api_url
        logger.info('Refreshing Courses and CourseRuns from %s...', api_url)
        response = self.api_client.courses.get()

        data = response['items']
        logger.info('Retrieved %d course runs...', len(data))

        for body in data:
            # NOTE (CCB): Some of the entries are empty arrays. We will fix this on the Drupal side of things
            # later (ECOM-4493). For now, ignore them.
            if not body:
                continue

            course_run_id = body['course_id']
            try:
                cleaned_body = self.clean_strings(body)
                course = self.update_course(cleaned_body)
                self.update_course_run(course, cleaned_body)
            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=api_url
                )
                logger.exception(msg)

        # Clean Organizations separately from other orphaned instances to avoid removing all orgnaziations
        # after an initial data load on an empty table.
        Organization.objects.filter(courseorganization__isnull=True, authored_programs__isnull=True,
                                    credit_backed_programs__isnull=True).delete()
        self.delete_orphans()

        logger.info('Retrieved %d course runs from %s.', len(data), api_url)

    def update_course(self, body):
        """Create or update a course from Drupal data given by `body`."""
        course_key = self.convert_course_run_key(body['course_id'])
        try:
            course = Course.objects.get(key=course_key)
        except Course.DoesNotExist:
            logger.warning('Course not find course [%s]', course_key)
            return None

        course.full_description = self.clean_html(body['description'])
        course.short_description = self.clean_html(body['subtitle'])
        course.partner = self.partner
        course.title = self.clean_html(body['title'])

        level_type, __ = LevelType.objects.get_or_create(name=body['level']['title'])
        course.level_type = level_type

        self.set_subjects(course, body)
        self.set_sponsors(course, body)

        course.save()
        return course

    def set_subjects(self, course, body):
        """Update `course` with subjects from `body`."""
        course.subjects.clear()
        subjects = (s['title'] for s in body['subjects'])
        subjects = Subject.objects.filter(name__in=subjects, partner=self.partner)
        course.subjects.add(*subjects)

    def set_sponsors(self, course, body):
        """Update `course` with sponsors from `body`."""
        course.courseorganization_set.filter(relation_type=CourseOrganization.SPONSOR).delete()
        for sponsor_body in body['sponsors']:
            image, __ = Image.objects.get_or_create(src=sponsor_body['image'])
            defaults = {
                'name': sponsor_body['title'],
                'logo_image': image,
                'homepage_url': urljoin(self.partner.marketing_site_url_root, sponsor_body['uri']),
            }
            organization, __ = Organization.objects.update_or_create(key=sponsor_body['uuid'], defaults=defaults)
            CourseOrganization.objects.create(
                course=course,
                organization=organization,
                relation_type=CourseOrganization.SPONSOR
            )

    def update_course_run(self, course, body):
        """
        Create or update a run of `course` from Drupal data given by `body`.
        """
        course_run_key = body['course_id']
        try:
            course_run = CourseRun.objects.get(key=course_run_key)
        except CourseRun.DoesNotExist:
            logger.warning('Could not find course run [%s]', course_run_key)
            return None

        course_run.language = self.get_language_tag(body)
        course_run.course = course
        course_run.marketing_url = urljoin(self.partner.marketing_site_url_root, body['course_about_uri'])
        course_run.start = self.parse_date(body['start'])
        course_run.end = self.parse_date(body['end'])
        course_run.image = self.get_courserun_image(body)

        self.set_staff(course_run, body)

        course_run.save()
        return course_run

    def set_staff(self, course_run, body):
        """Update `course_run` with staff from `body`."""
        course_run.staff.clear()
        for staff_body in body['staff']:
            image, __ = Image.objects.get_or_create(src=staff_body['image'])
            defaults = {
                'name': staff_body['title'],
                'profile_image': image,
                'title': staff_body['display_position']['title'],
            }
            person, __ = Person.objects.update_or_create(key=staff_body['uuid'], defaults=defaults)
            course_run.staff.add(person)

    def get_language_tag(self, body):
        """Get a language tag from Drupal data given by `body`."""
        iso_code = body['current_language']
        if iso_code is None:
            return None

        # NOTE (CCB): Default to U.S. English for edx.org to avoid spewing
        # unnecessary warnings.
        if iso_code == 'en':
            iso_code = 'en-us'

        try:
            return LanguageTag.objects.get(code=iso_code)
        except LanguageTag.DoesNotExist:
            logger.warning('Could not find language with ISO code [%s].', iso_code)
            return None

    def get_courserun_image(self, body):
        image = None
        image_url = body['image']

        if image_url:
            image, __ = Image.objects.get_or_create(src=image_url)

        return image


class AbstractMarketingSiteDataLoader(AbstractDataLoader):
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
        return {}

    def ingest(self):
        """ Load data for all supported objects (e.g. courses, runs). """
        page = 0
        query_kwargs = self.get_query_kwargs()

        while page is not None and page >= 0:  # pragma: no cover
            kwargs = {
                'type': self.node_type,
                'max-depth': 2,
                'load-entity-refs': 'subject,file,taxonomy_term,taxonomy_vocabulary,node,field_collection_item',
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

        try:
            program = Program.objects.get(marketing_slug=marketing_slug, partner=self.partner)
        except Program.DoesNotExist:
            logger.error('Program [%s] exists on the marketing site, but not in the Programs Service!', marketing_slug)
            return None

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
            'video': self.get_or_create_video(video_url)
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
