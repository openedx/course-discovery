import datetime
from functools import partial
from itertools import product

import pytest
import pytz

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import SeatFactory


@pytest.fixture(scope='class')
def course_run_states(request):
    """
    pytest fixture for providing test classes with attributes necessary to create
    and test CourseRuns in all states affecting availability.
    """
    # Set class attributes on the invoking test context.
    request.cls.states, request.cls.available_states = get_course_run_states()


def get_course_run_states():
    """
    Utility method to get course_run_states and available_states.
    """
    now = datetime.datetime.now(pytz.UTC)
    past = now - datetime.timedelta(days=30)
    future = now + datetime.timedelta(days=30)

    def enrollment_start_null(course_run):
        course_run.enrollment_start = None

    def enrollment_start_past(course_run):
        course_run.enrollment_start = past

    def enrollment_start_future(course_run):
        course_run.enrollment_start = future

    def enrollment_end_null(course_run):
        course_run.enrollment_end = None

    def enrollment_end_past(course_run):
        course_run.enrollment_end = past

    def enrollment_end_future(course_run):
        course_run.enrollment_end = future

    def end_null(course_run):
        course_run.end = None

    def end_past(course_run):
        course_run.end = past

    def end_future(course_run):
        course_run.end = future

    def seats_null(course_run):  # pylint: disable=unused-argument
        pass

    def seats_exist(course_run):
        SeatFactory(course_run=course_run)

    def published(course_run):
        course_run.status = CourseRunStatus.Published

    def unpublished(course_run):
        course_run.status = CourseRunStatus.Unpublished

    # The Cartesian product of these lists represents the 216 possible course
    # run states that affect a parent course's availability.
    states = [
        [
            enrollment_start_null,
            enrollment_start_past,
            enrollment_start_future
        ],
        [
            enrollment_end_null,
            enrollment_end_past,
            enrollment_end_future
        ],
        [
            end_null,
            end_past,
            end_future
        ],
        [
            seats_null,
            seats_exist
        ],
        [
            published,
            unpublished
        ]
    ]

    # The Cartesian product of these lists represents the 8 possible course
    # run states that yield an available parent course.
    available_states = [
        [
            enrollment_start_null,
            enrollment_start_past
        ],
        [
            enrollment_end_null,
            enrollment_end_future
        ],
        [
            end_null,
            end_future
        ],
        [
            seats_exist
        ],
        [
            published
        ]
    ]

    return partial(product, *states), list(product(*available_states))
