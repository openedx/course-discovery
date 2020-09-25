import logging
import math

from django.db.models.fields.related import ManyToManyField
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey
from sortedm2m.fields import SortedManyToManyField

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.models import CourseRun

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
        return None

    return cast2int(request.query_params.get(name), name)


def reviewable_data_has_changed(obj, new_key_vals, exempt_fields=None):
    """
    Check whether serialized data for the object has changed.

    Args:
        obj (Object): Object representing the persisted state
        new_key_vals (dict_items): List of (key,value) tuples representing the new state
        exempt_fields (list): List of field names where a change does not affect review status

    Returns:
        bool for whether data for any reviewable fields has changed
    """
    changed = False
    exempt_fields = exempt_fields or []
    for key, new_value in [x for x in new_key_vals if x[0] not in exempt_fields]:
        original_value = getattr(obj, key, None)
        if isinstance(new_value, list):
            field_class = obj.__class__._meta.get_field(key).__class__
            original_value_elements = original_value.all()
            if len(new_value) != original_value_elements.count():
                changed = True
            # Just use set compare since none of our fields require duplicates
            elif field_class == ManyToManyField and set(new_value) != set(original_value_elements):
                changed = True
            elif field_class == SortedManyToManyField:
                for new_value_element, original_value_element in zip(new_value, original_value_elements):
                    if new_value_element != original_value_element:
                        changed = True
        elif new_value != original_value:
            changed = True
    return changed


def conditional_decorator(condition, decorator):
    """
    Util decorator that allows for only using the given decorator arg if the condition passes
    """
    return decorator if condition else lambda x: x


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
        run = f'{trimester}T{start.year}'

        related_course_runs = CourseRun.everything.filter(key__contains=course_num).values_list('key', flat=True)
        related_course_runs = [CourseKey.from_string(key).run for key in related_course_runs]

        return cls._get_next_run(run, '', related_course_runs)

    @classmethod
    def generate_data_for_studio_api(cls, course_run, creating, user=None):
        editors = [editor.user for editor in course_run.course.editors.all()]
        key = CourseKey.from_string(course_run.key)

        # start, end, and pacing are not sent on updates - Studio is where users edit them
        start = course_run.start if creating else None
        end = course_run.end if creating else None
        pacing = course_run.pacing_type if creating else None

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
                           'course run being created without a course team.', key.course)

        data = {
            'title': course_run.title,
            'org': key.org,
            'number': key.course,
            'run': key.run,
            'team': team,
        }

        if pacing:
            data['pacing_type'] = pacing

        if start or end:
            data['schedule'] = {
                'start': serialize_datetime(start),
                'end': serialize_datetime(end),
            }

        return data

    def create_course_rerun_in_studio(self, course_run, old_course_run_key, user=None):
        data = self.generate_data_for_studio_api(course_run, creating=True, user=user)
        return self._api.course_runs(old_course_run_key).rerun.post(data)

    def create_course_run_in_studio(self, publisher_course_run, user=None):
        data = self.generate_data_for_studio_api(publisher_course_run, creating=True, user=user)
        return self._api.course_runs.post(data)

    def update_course_run_image_in_studio(self, course_run):
        course = course_run.course
        image = course.image

        if image:
            files = {'card_image': image}
            try:
                self._api.course_runs(course_run.key).images.post(files=files)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    _('An error occurred while setting the course run image for [{key}] in studio. All other fields '
                      'were successfully saved in Studio.').format(key=course_run.key)
                )
        else:
            logger.warning(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                course_run.id,
                course.id
            )

    def update_course_run_details_in_studio(self, course_run):
        data = self.generate_data_for_studio_api(course_run, creating=False)
        # NOTE: We use PATCH to avoid overwriting existing team data that may have been manually input in Studio.
        return self._api.course_runs(course_run.key).patch(data)

    def push_to_studio(self, course_run, create=False, old_course_run_key=None, user=None):
        if create and old_course_run_key:
            response = self.create_course_rerun_in_studio(course_run, old_course_run_key, user=user)
        elif create:
            response = self.create_course_run_in_studio(course_run, user=user)
        else:
            response = self.update_course_run_details_in_studio(course_run)

        return response
