"""
tests for learner_pathway app.
"""
import datetime
from unittest import mock
from django.test import TestCase
import pytz

from course_discovery.apps.learner_pathway.models import LearnerPathwayCourse
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, SeatFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours

import logging
logging.disable(logging.WARN)

class LearnerPathwayCourseTests(TestCase):
    """ Tests for the LearnerPathwayCourse Model """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory()

        TWO_WEEKS_FROM_TODAY = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=14)
        YESTERDAY = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        self.advertised_course_run = CourseRunFactory(
            start=YESTERDAY,
            end=TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Published,
            # enrollment_end=TWO_WEEKS_FROM_TODAY,
            min_effort=5,
            max_effort=8,
            weeks_to_complete=8,
            course=self.course,
            enrollment_start=None,
            enrollment_end=None,
        )
        SeatFactory(course_run=self.advertised_course_run)

    def test_get_estimated_time_of_completion(self):
        """ Verify that `get_estimated_time_of_completion` method is working as expected """
        learner_pathway_course = LearnerPathwayCourse(course=self.course)
        estimated_time_of_completion = learner_pathway_course.get_estimated_time_of_completion()
        assert estimated_time_of_completion == get_course_run_estimated_hours(self.advertised_course_run)

    def test_get_skills(self):
        """ Verify that `get_skills` method is working as expected """
        expected_skills = [{'name': 'skill name 1', 'description': 'skill description 1'}]
        learner_pathway_course = LearnerPathwayCourse(course=self.course)
        with mock.patch(
            'course_discovery.apps.learner_pathway.models.get_whitelisted_serialized_skills',
            return_value=expected_skills
        ):
            skills = learner_pathway_course.get_skills()
            assert skills == expected_skills