import logging
import math

from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.core.utils import serialize_datetime

logger = logging.getLogger(__name__)


class StudioAPI:
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
    def calculate_course_run_key_run_value(cls, course_run):
        start = course_run.start
        trimester = math.ceil(start.month / 4.)
        run = '{trimester}T{year}'.format(trimester=trimester, year=start.year)

        try:
            discovery_course = course_run.course.discovery_counterpart
        except:  # pylint:disable=bare-except
            logger.exception('Failed to get Discovery counterpart for Publisher course [%d]', course_run.course.id)
            return run

        related_course_runs = discovery_course.course_runs.values_list('key', flat=True)
        related_course_runs = [CourseKey.from_string(key).run for key in related_course_runs]
        return cls._get_next_run(run, '', related_course_runs)

    @classmethod
    def generate_data_for_studio_api(cls, publisher_course_run):
        course = publisher_course_run.course
        course_team_admin = course.course_team_admin
        team = []

        if course_team_admin:
            team = [
                {
                    'user': course_team_admin.username,
                    'role': 'instructor',
                },
            ]
        else:
            logger.warning('No course team admin specified for course [%s]. This may result in a Studio '
                           'course run being created without a course team.', course.number)

        return {
            'title': publisher_course_run.title_override or course.title,
            'org': course.organizations.first().key,
            'number': course.number,
            'run': cls.calculate_course_run_key_run_value(publisher_course_run),
            'schedule': {
                'start': serialize_datetime(publisher_course_run.start),
                'end': serialize_datetime(publisher_course_run.end),
            },
            'team': team,
            'pacing_type': publisher_course_run.pacing_type,
        }

    def create_course_rerun_in_studio(self, publisher_course_run, discovery_course_run):
        data = self.generate_data_for_studio_api(publisher_course_run)
        return self._api.course_runs(discovery_course_run.key).rerun.post(data)

    def create_course_run_in_studio(self, publisher_course_run):
        data = self.generate_data_for_studio_api(publisher_course_run)
        return self._api.course_runs.post(data)

    def update_course_run_image_in_studio(self, publisher_course_run):
        course = publisher_course_run.course
        image = course.image

        if image:
            files = {'card_image': image}
            return self._api.course_runs(publisher_course_run.lms_course_id).images.post(files=files)
        else:
            logger.warning(
                'Card image for course run [%d] cannot be updated. The related course [%d] has no image defined.',
                publisher_course_run.id,
                course.id
            )

    def update_course_run_details_in_studio(self, publisher_course_run):
        data = self.generate_data_for_studio_api(publisher_course_run)
        # NOTE: We use PATCH to avoid overwriting existing team data that may have been manually input in Studio.
        return self._api.course_runs(publisher_course_run.lms_course_id).patch(data)
