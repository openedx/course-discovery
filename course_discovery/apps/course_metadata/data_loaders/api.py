import concurrent.futures
from datetime import datetime
import logging
import math
import time
from decimal import Decimal
from io import BytesIO

import requests
from django.core.files import File
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Organization, Program, ProgramType, Seat, SeatType, Video
)

logger = logging.getLogger(__name__)


class OrganizationsApiDataLoader(AbstractDataLoader):
    """ Loads organizations from the Organizations API. """

    def ingest(self):
        api_url = self.partner.organizations_api_url
        count = None
        page = 1

        logger.info('Refreshing Organizations from %s...', api_url)

        while page:
            response = self.api_client.organizations().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d organizations...', len(results))

            if response['next']:
                page += 1
            else:
                page = None
            for body in results:
                body = self.clean_strings(body)
                self.update_organization(body)

        logger.info('Retrieved %d organizations from %s.', count, api_url)

        self.delete_orphans()

    def update_organization(self, body):
        key = body['short_name']
        logo = body['logo']

        defaults = {
            'key': key,
            'partner': self.partner,
            'certificate_logo_image_url': logo,
        }

        if not self.partner.has_marketing_site:
            defaults.update({
                'name': body['name'],
                'description': body['description'],
                'logo_image_url': logo,
            })

        Organization.objects.update_or_create(key__iexact=key, partner=self.partner, defaults=defaults)
        logger.info('Processed organization "%s"', key)


class CoursesApiDataLoader(AbstractDataLoader):
    """ Loads course runs from the Courses API. """

    def __init__(
            self,
            partner, api_url, access_token=None,
            token_type=None, max_workers=None,
            is_threadsafe=False, **kwargs
    ):
        super(CoursesApiDataLoader, self).__init__(
            partner=partner, api_url=api_url, access_token=access_token,
            token_type=token_type, max_workers=max_workers,
            is_threadsafe=is_threadsafe, **kwargs
        )
        self.target_course_key = kwargs.pop('course_key', None)

    def ingest(self):
        logger.info('Refreshing Courses and CourseRuns from %s...', self.partner.courses_api_url)

        initial_page = 1
        setattr(self, 'course_count', 0)
        setattr(self, 'loaded_course_keys', set())
        response = self._make_request(initial_page)
        count = response['pagination']['count']
        pages = response['pagination']['num_pages']
        self._process_response(response)

        if not self.course_count:
            self.course_count = count

        pagerange = range(initial_page + 1, pages + 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:  # pragma: no cover
            if self.is_threadsafe:
                for page in pagerange:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    executor.submit(self._load_data, page)
            else:
                for future in [executor.submit(self._make_request, page) for page in pagerange]:
                    # This time.sleep is to make it very likely that this method does not encounter a 429 status
                    # code by increasing the amount of time between each code. More details at LEARNER-5560
                    # The current crude estimation is for ~3000 courses with a PAGE_SIZE=50 which means this method
                    # will take ~30 minutes.
                    # TODO Ticket to gracefully handle 429 https://openedx.atlassian.net/browse/LEARNER-5565
                    time.sleep(30)
                    response = future.result()
                    self._process_response(response)

        logger.info('Retrieved %d course runs from %s.', count, self.partner.courses_api_url)

        self.delete_orphans()
        self.delete_expired_courses()

    @property
    def is_loading_all_courses(self):
        return not self.modified_x_min_ago and not self.target_course_key

    def delete_expired_courses(self):
        if self.is_loading_all_courses:
            logger.info(
                '*** Maintaining course list...... ( Cached Course number={}, Loaded Course number={} )'.format(
                    len(self.loaded_course_keys), self.course_count
                )
            )

            from course_discovery.apps.core.utils import delete_expired_courses

            if len(self.loaded_course_keys) == self.course_count:
                local_course_keys = {r['key'] for r in CourseRun.objects.values('key').all()}
                removed_course_keys = local_course_keys - self.loaded_course_keys

                if removed_course_keys:
                    delete_expired_courses(self.partner, removed_course_keys)

            else:
                logger.error(
                    '*** Integrity Error of loaded course keys ( Loaded Number({}) != Expect Number({}) )'.format(
                        len(self.loaded_course_keys), self.course_count
                    )
                )

    def _load_data(self, page):  # pragma: no cover
        """Make a request for the given page and process the response."""
        response = self._make_request(page)
        self._process_response(response)

    def _make_request(self, page):
        """Make incremental query ( load new edited courses in 24 hours Only ) if out of `Maintenance Period`,
            Otherwise load all of courses from LMS.
        """
        if self.modified_x_min_ago:
            logger.info('*** Query incremental courses from LMS. page_no={}'.format(page))
            return self.api_client.courses().get(
                page=page, page_size=self.PAGE_SIZE,
                username=self.username,
                org=self.partner.short_code,
                modified_in_minutes=self.modified_x_min_ago   # Only query new edited courses in one hour from LMS
            )

        else:
            if self.target_course_key:
                logger.info('*** Query Target Course => [ {} ] from LMS.'.format(self.target_course_key))
            else:
                logger.info('*** Query all of courses from LMS. page_no={}'.format(page))

            kwargs = {
                'page': page, 'page_size': self.PAGE_SIZE,
                'username': self.username, 'org': self.partner.short_code
            }
            if self.target_course_key:
                kwargs['id'] = self.target_course_key

            return self.api_client.courses().get(**kwargs)

    def _process_response(self, response):
        results = response['results']

        logger.info(
            'Retrieved {} {}...'.format(len(results), 'Course Keys' if self.is_loading_all_courses else 'Course runs')
        )

        for body in results:
            course_run_id = body['id']

            if self.is_loading_all_courses or self.target_course_key:
                # Loading course key Only...
                self.loaded_course_keys.add(course_run_id)

            try:
                body = self.clean_strings(body)
                course_run = self.get_course_run(body)
                if course_run:
                    self.update_course_run(course_run, body)
                    course = getattr(course_run, 'canonical_for_course', False)
                    if course and not self.partner.has_marketing_site:
                        # If the partner have marketing site,
                        # we should only update the course information from the marketing site.
                        # Therefore, we don't need to do the statements below
                        course = self.update_course(course, body)
                        logger.info('Processed course with key [%s].', course.key)
                else:
                    course, created = self.get_or_create_course(body)
                    course_run = self.create_course_run(course, body)
                    if created:
                        course.canonical_course_run = course_run
                        course.save()
            except:  # pylint: disable=bare-except
                msg = 'An error occurred while updating {course_run} from {api_url}'.format(
                    course_run=course_run_id,
                    api_url=self.partner.courses_api_url
                )
                logger.exception(msg)

    def get_course_run(self, body):
        course_run_key = body['id']
        try:
            return CourseRun.objects.get(key__iexact=course_run_key)
        except CourseRun.DoesNotExist:
            return None

    def update_course_run(self, course_run, body):
        validated_data = self.format_course_run_data(body)
        self._update_instance(course_run, validated_data, suppress_publication=True)

        logger.info('Processed course run with UUID [%s].', course_run.uuid)

    def create_course_run(self, course, body):
        defaults = self.format_course_run_data(body, course=course)

        return CourseRun.objects.create(**defaults)

    def get_or_create_course(self, body):
        course_run_key = CourseKey.from_string(body['id'])
        course_key = self.get_course_key_from_course_run_key(course_run_key)
        defaults = self.format_course_data(body)
        # We need to add the key to the defaults because django ignores kwargs with __
        # separators when constructing the create request
        defaults['key'] = course_key
        defaults['partner'] = self.partner

        course, created = Course.objects.get_or_create(
            key__iexact=course_key, partner=self.partner, defaults=defaults
        )

        return (course, created)

    def update_course(self, course, body):
        validated_data = self.format_course_data(body)
        self._update_instance(course, validated_data)

        logger.info('Processed course with key [%s].', course.key)

        return course

    def _update_instance(self, instance, validated_data, **kwargs):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(**kwargs)

    def format_course_run_data(self, body, course=None):
        defaults = {
            'key': body['id'],
            'end': self.parse_date(body['end']),
            'enrollment_start': self.parse_date(body['enrollment_start']),
            'enrollment_end': self.parse_date(body['enrollment_end']),
        }

        # When using a marketing site, only dates (excluding start) should come from the Course API.
        if not self.partner.has_marketing_site:
            defaults.update({
                'start': self.parse_date(body['start']),
                'title_override': body['name'],
                'status': CourseRunStatus.Published,
            })

        if course:
            defaults['course'] = course

        return defaults

    def format_course_data(self, body):
        defaults = {
            'title': body['name'],
        }

        if not self.partner.has_marketing_site:
            defaults['card_image_url'] = body['media'].get('image', {}).get('raw')

        return defaults


class ProgramsApiDataLoader(AbstractDataLoader):
    """ Loads programs from the Programs API. """
    image_width = 1440
    image_height = 480
    XSERIES = None

    def __init__(self, partner, api_url, access_token=None, token_type=None, max_workers=None,
                 is_threadsafe=False, **kwargs):
        super(ProgramsApiDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )
        self.XSERIES = ProgramType.objects.get(name='XSeries')

    def ingest(self):
        api_url = self.partner.programs_api_url
        count = None
        page = 1

        logger.info('Refreshing programs from %s...', api_url)

        while page:
            response = self.api_client.programs.get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d programs...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for program in results:
                program = self.clean_strings(program)
                self.update_program(program)

        logger.info('Retrieved %d programs from %s.', count, api_url)

    def _get_uuid(self, body):
        return body['uuid']

    def update_program(self, body):
        uuid = self._get_uuid(body)

        try:
            defaults = {
                'uuid': uuid,
                'title': body['name'],
                'subtitle': body['subtitle'],
                'type': self.XSERIES,
                'status': body['status'],
                'banner_image_url': self._get_banner_image_url(body),
            }

            program, __ = Program.objects.update_or_create(
                marketing_slug=body['marketing_slug'],
                partner=self.partner,
                defaults=defaults
            )
            self._update_program_organizations(body, program)
            self._update_program_courses_and_runs(body, program)
            self._update_program_banner_image(body, program)
            program.save()
        except Exception:  # pylint: disable=broad-except
            logger.exception('Failed to load program %s', uuid)

    def _update_program_courses_and_runs(self, body, program):
        course_run_keys = set()
        for course_code in body.get('course_codes', []):
            course_run_keys.update([course_run['course_key'] for course_run in course_code['run_modes']])

        # The course_code key field is technically useless, so we must build the course list from the
        # associated course runs.
        courses = Course.objects.filter(course_runs__key__in=course_run_keys).distinct()
        program.courses.clear()
        program.courses.add(*courses)

        # Do a diff of all the course runs and the explicitly-associated course runs to determine
        # which course runs should be explicitly excluded.
        excluded_course_runs = CourseRun.objects.filter(course__in=courses).exclude(key__in=course_run_keys)
        program.excluded_course_runs.clear()
        program.excluded_course_runs.add(*excluded_course_runs)

    def _update_program_organizations(self, body, program):
        uuid = self._get_uuid(body)
        org_keys = [org['key'] for org in body['organizations']]
        organizations = Organization.objects.filter(key__in=org_keys, partner=self.partner)

        if len(org_keys) != organizations.count():
            logger.error('Organizations for program [%s] are invalid!', uuid)

        program.authoring_organizations.clear()
        program.authoring_organizations.add(*organizations)

    def _get_banner_image_url(self, body):
        image_key = 'w{width}h{height}'.format(width=self.image_width, height=self.image_height)
        image_url = body.get('banner_image_urls', {}).get(image_key)
        return image_url

    def _update_program_banner_image(self, body, program):
        image_url = self._get_banner_image_url(body)
        if not image_url:
            logger.warning('There are no banner image url for program %s', program.title)
            return

        r = requests.get(image_url)
        if r.status_code == 200:
            banner_downloaded = File(BytesIO(r.content))
            program.banner_image.save(
                'banner.jpg',
                banner_downloaded
            )
            program.save()
        else:
            logger.exception('Loading the banner image %s for program %s failed', image_url, program.title)
