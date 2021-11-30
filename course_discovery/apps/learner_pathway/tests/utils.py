import datetime

import pytz

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, SeatFactory


def generate_course():
    course = CourseFactory()
    TWO_WEEKS_FROM_TODAY = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=14)
    YESTERDAY = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
    advertised_course_run = CourseRunFactory(
        start=YESTERDAY,
        end=TWO_WEEKS_FROM_TODAY,
        status=CourseRunStatus.Published,
        min_effort=5,
        max_effort=8,
        weeks_to_complete=8,
        course=course,
        enrollment_start=None,
        enrollment_end=None,
    )
    SeatFactory(course_run=advertised_course_run)
    return (course, advertised_course_run)
