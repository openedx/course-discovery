import concurrent.futures
import logging
import time

from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Course, CourseRun


logger = logging.getLogger(__name__)


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
        self._update_instance(course_run, validated_data)

        logger.info('Processed course run with UUID [%s].', course_run.uuid)

    def create_course_run(self, course, body):
        defaults = self.format_course_run_data(body, course=course)

        return CourseRun.objects.create(**defaults)

    def get_or_create_course(self, body):
        course_key = CourseKey.from_string(body['id'])
        course_key_str = str(course_key)
        defaults = self.format_course_data(course_key, body)
        # We need to add the key to the defaults because django ignores kwargs with __
        # separators when constructing the create request
        defaults['key'] = course_key_str
        defaults['org'] = course_key.org

        course, created = Course.objects.get_or_create(
            key__iexact=course_key_str,
            defaults=defaults
        )

        return (course, created)

    def update_course(self, course, body):
        course_key = CourseKey.from_string(body['id'])
        validated_data = self.format_course_data(course_key, body)
        self._update_instance(course, validated_data)

        logger.info('Processed course with key [{}] | org [{}].'.format(course.key, course_key.org))

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

    def format_course_data(self, course_key, body):
        defaults = {
            'title': body['name'],
            'org': course_key.org
        }

        if not self.partner.has_marketing_site:
            defaults['card_image_url'] = body['media'].get('image', {}).get('raw')

        return defaults
