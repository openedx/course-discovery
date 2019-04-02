import hashlib
import logging
import math
import six

from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.models import CourseRun as DiscoveryCourseRun

logger = logging.getLogger(__name__)


def cast2int(value, name):
    """
    Attempt to cast the provided value to an integer.

    Arguments:
        value (str): A value to cast to an integer.
        name (str): A name to log if casting fails.

    Raises:
        ValueError, if the provided value can't be converted. A helpful
            error message is logged first.

    Returns:
        int | None
    """
    if value is None:
        return value

    try:
        return int(value)
    except ValueError:
        logger.exception('The "%s" parameter requires an integer value. "%s" is invalid.', name, value)
        raise


def get_query_param(request, name):
    """
    Get a query parameter and cast it to an integer.
    """
    # This facilitates DRF's schema generation. For more, see
    # https://github.com/encode/django-rest-framework/blob/3.6.3/rest_framework/schemas.py#L383
    if request is None:
        return

    return cast2int(request.query_params.get(name), name)


def get_cache_key(**kwargs):
    """
    Get MD5 encoded cache key for given arguments.

    Here is the format of key before MD5 encryption.
        key1:value1__key2:value2 ...

    Example:
        >>> get_cache_key(site_domain="example.com", resource="catalogs")
        # Here is key format for above call
        # "site_domain:example.com__resource:catalogs"
        a54349175618ff1659dee0978e3149ca

    Arguments:
        **kwargs: Key word arguments that need to be present in cache key.

    Returns:
         An MD5 encoded key uniquely identified by the key word arguments.
    """
    key = '__'.join(['{}:{}'.format(item, value) for item, value in six.iteritems(kwargs)])

    return hashlib.md5(key.encode('utf-8')).hexdigest()


class StudioAPI:
    """
    A convenience class for talking to the Studio API - designed to allow subclassing by the publisher django app,
    so that they can use it for their own publisher CourseRun models, which are slightly different than the course
    metadata ones.
    """

    def __init__(self, api_client):
        self._api = api_client

    @classmethod
    def _get_next_run(cls, root, suffix, existing_runs):
        candidate = root + suffix

        if candidate in existing_runs:
            # If our candidate is an existing run, use the next letter in the alphabet as the
            # run suffix (e.g. 1T2017, 1T2017a, 1T2017b, ...).
            suffix = chr(ord(suffix) + 1) if suffix else 'a'
            return cls._get_next_run(root, suffix, existing_runs)

        return candidate

    @classmethod
    def calculate_course_run_key_run_value(cls, course_num, start):
        trimester = math.ceil(start.month / 4.)
        run = '{trimester}T{year}'.format(trimester=trimester, year=start.year)

        related_course_runs = DiscoveryCourseRun.everything.filter(
            key__contains=course_num
        ).values_list('key', flat=True)

        related_course_runs = [CourseKey.from_string(key).run for key in related_course_runs]
        return cls._get_next_run(run, '', related_course_runs)

    @classmethod
    def generate_data_for_studio_api(cls, course_run, user=None):
        editors = cls._run_editors(course_run)
        org, number, run = cls._run_key_parts(course_run)
        start, end = cls._run_times(course_run)

        if user:
            editors.append(user)

        if editors:
            team = [
                {
                    'user': user.username,
                    'role': 'instructor',
                }
                for user in editors
            ]
        else:
            team = []
            logger.warning('No course team admin specified for course [%s]. This may result in a Studio '
                           'course run being created without a course team.', number)

        return {
            'title': cls._run_title(course_run),
            'org': org,
            'number': number,
            'run': run,
            'schedule': {
                'start': serialize_datetime(start),
                'end': serialize_datetime(end),
            },
            'team': team,
            'pacing_type': cls._run_pacing(course_run),
        }

    def create_course_rerun_in_studio(self, course_run, old_run, user=None):
        data = self.generate_data_for_studio_api(course_run, user=user)
        return self._api.course_runs(old_run.key).rerun.post(data)

    def create_course_run_in_studio(self, publisher_course_run, user=None):
        data = self.generate_data_for_studio_api(publisher_course_run, user=user)
        return self._api.course_runs.post(data)

    def update_course_run_image_in_studio(self, course_run, run_response=None):
        course = course_run.course
        image = course.image

        if image:
            files = {'card_image': image}
            return self._api.course_runs(self._run_key(course_run, run_response)).images.post(files=files)
        else:
            logger.warning(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                course_run.id,
                course.id
            )

    def update_course_run_details_in_studio(self, course_run):
        data = self.generate_data_for_studio_api(course_run)
        # NOTE: We use PATCH to avoid overwriting existing team data that may have been manually input in Studio.
        return self._api.course_runs(self._run_key(course_run)).patch(data)

    def push_to_studio(self, course_run, create=False, old_course_run=None, user=None):
        if create and old_course_run:
            response = self.create_course_rerun_in_studio(course_run, old_course_run, user=user)
        elif create:
            response = self.create_course_run_in_studio(course_run, user=user)
        else:
            response = self.update_course_run_details_in_studio(course_run)

        self.update_course_run_image_in_studio(course_run, run_response=response)
        return response

    @classmethod
    def _run_key(cls, course_run, run_response=None):  # pylint: disable=unused-argument
        return course_run.key

    @classmethod
    def _run_key_parts(cls, course_run):
        key = CourseKey.from_string(course_run.key)
        return key.org, key.course, key.run

    @classmethod
    def _run_title(cls, course_run):
        return course_run.title

    @classmethod
    def _run_times(cls, course_run):
        return course_run.start, course_run.end

    @classmethod
    def _run_pacing(cls, course_run):
        return course_run.pacing_type

    @classmethod
    def _run_editors(cls, course_run):
        return [editor.user for editor in course_run.course.editors.all()]
