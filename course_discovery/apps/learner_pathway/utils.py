"""
Utils for learner_pathway app.
"""
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours


def get_advertised_course_run_estimated_hours(course):
    active_course_runs = course.active_course_runs
    if course.advertised_course_run:
        advertised_course_run_uuid = course.advertised_course_run.uuid
        for course_run in active_course_runs:
            if course_run.uuid == advertised_course_run_uuid:
                return get_course_run_estimated_hours(course_run)

    return None
