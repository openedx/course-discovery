import datetime
from unittest import mock

import ddt
import pytest
import pytz
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, SeatFactory
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from course_discovery.apps.learner_pathway.models import LearnerPathwayCourse
from course_discovery.apps.learner_pathway.tests import factories


@pytest.mark.django_db
@ddt.ddt
class LearnerPathwayTests(TestCase):
    """ LearnerPathway model tests. """

    def setUp(self):
        super().setUp()
        self.learner_pathway_step_1 = factories.LearnerPathwayStepFactory()
        self.learner_pathway_step_2 = factories.LearnerPathwayStepFactory(pathway=self.learner_pathway_step_1.pathway)
        self.learner_pathway_step_3 = factories.LearnerPathwayStepFactory(pathway=self.learner_pathway_step_1.pathway)
        self.learner_pathway_step_other_pathway = factories.LearnerPathwayStepFactory()
        self.learner_pathway = self.learner_pathway_step_1.pathway

    def test_learner_pathway_time_of_completion(self):
        """ Validate that model aggregates the time to completion correctly. """
        with mock.patch(
                'course_discovery.apps.learner_pathway.models.LearnerPathwayStep.get_estimated_time_of_completion',
                return_value=10.0
        ):
            self.assertEqual(
                self.learner_pathway.time_of_completion,
                self.learner_pathway_step_1.get_estimated_time_of_completion() * 3
            )

    def test_learner_pathway_skills(self):
        """ Validate that model aggregates the skills correctly. """
        with mock.patch(
                'course_discovery.apps.learner_pathway.models.LearnerPathwayStep.get_skills',
                return_value=[
                    {'name': 'skill-1', 'description': 'skill-1-description'},
                    {'name': 'skill-2', 'description': 'skill-2-description'}
                ]
        ):
            self.assertEqual(
                self.learner_pathway.skills,
                self.learner_pathway_step_1.get_skills()
            )


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
            min_effort=5,
            max_effort=8,
            weeks_to_complete=8,
            course=self.course,
            enrollment_start=None,
            enrollment_end=None,
        )
        SeatFactory(course_run=self.advertised_course_run)
        self.step = factories.LearnerPathwayStepFactory()

    def test_get_estimated_time_of_completion(self):
        """ Verify that `LearnerPathwayCourse.get_estimated_time_of_completion` method is working as expected """
        learner_pathway_course = LearnerPathwayCourse.objects.create(course=self.course, step=self.step)
        estimated_time_of_completion = learner_pathway_course.get_estimated_time_of_completion()
        assert estimated_time_of_completion == get_course_run_estimated_hours(self.advertised_course_run)

    def test_get_skills(self):
        """ Verify that `LearnerPathwayCourse.get_skills` method is working as expected """

        expected_skills = [{'name': 'skill name 1', 'description': 'skill description 1'}]
        learner_pathway_course = LearnerPathwayCourse(course=self.course)
        with mock.patch(
            'course_discovery.apps.learner_pathway.models.get_whitelisted_serialized_skills',
            return_value=expected_skills
        ):
            skills = learner_pathway_course.get_skills()
            assert skills == expected_skills
