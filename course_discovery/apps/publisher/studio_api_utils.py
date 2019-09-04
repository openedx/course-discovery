from course_discovery.apps.api.utils import StudioAPI as StudioAPIBase


class StudioAPI(StudioAPIBase):
    """ A version of StudioAPI that knows how to talk to our publisher models. """

    @classmethod
    def _run_key(cls, course_run, run_response=None):
        return course_run.lms_course_id or (run_response and run_response.get('id'))

    @classmethod
    def _run_key_parts(cls, course_run):
        course = course_run.course
        run = cls.calculate_course_run_key_run_value(course.number, course_run.start_date_temporary)
        return course.organizations.first().key, course.number, run

    @classmethod
    def _run_title(cls, course_run):
        return course_run.title_override or course_run.course.title

    @classmethod
    def _run_times(cls, course_run, creating):
        # We don't use the creating param - normal StudioAPI uses it to only send dates when creating.
        # But for historical reasons, we always push them. (rest of system is moving to Studio as the
        # only place these dates get edited, but we are from an older time and didn't want to change it)
        return course_run.start_date_temporary, course_run.end_date_temporary

    @classmethod
    def _run_pacing(cls, course_run):
        return course_run.pacing_type_temporary

    @classmethod
    def _run_editors(cls, course_run):
        if course_run.course.course_team_admin:
            return [course_run.course.course_team_admin]
        else:
            return []
