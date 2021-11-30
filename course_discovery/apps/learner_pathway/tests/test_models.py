from unittest import mock

import ddt
import pytest
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import ProgramFactory
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from course_discovery.apps.learner_pathway.models import LearnerPathwayCourse, LearnerPathwayProgram
from course_discovery.apps.learner_pathway.tests import factories
from course_discovery.apps.learner_pathway.tests.utils import generate_course


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
        self.course, self.advertised_course_run = generate_course()
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


class LearnerPathwayProgramTests(TestCase):
    """ Tests for the LearnerPathwayProgram Model """

    def setUp(self):
        super().setUp()
        self.course1, self.course_run1 = generate_course()
        self.course2, self.course_run2 = generate_course()
        self.program = ProgramFactory(courses=[self.course1, self.course2])
        self.step = factories.LearnerPathwayStepFactory()
        self.learner_pathway_program = LearnerPathwayProgram.objects.create(program=self.program, step=self.step)

    def test_get_estimated_time_of_completion(self):
        """ Verify that `LearnerPathwayProgram.get_estimated_time_of_completion` method is working as expected """

        program_estimated_time_of_completion = self.learner_pathway_program.get_estimated_time_of_completion()
        assert program_estimated_time_of_completion == get_course_run_estimated_hours(
            self.course_run1
        ) + get_course_run_estimated_hours(
            self.course_run2
        )

    def test_get_skills(self):
        """ Verify that `LearnerPathwayProgram.get_skills` method is working as expected """

        expected_skills = [{'name': 'skill name 1', 'description': 'skill description 1'}]
        with mock.patch(
            'course_discovery.apps.learner_pathway.models.get_whitelisted_serialized_skills',
            return_value=expected_skills
        ):
            program_skills = self.learner_pathway_program.get_skills()
            assert program_skills == expected_skills + expected_skills


class LearnerPathwayStepTests(TestCase):
    """ Tests for the LearnerPathwayStep Model """

    def setUp(self):
        super().setUp()
        self.course, _ = generate_course()
        self.step = factories.LearnerPathwayStepFactory()
        self.learner_pathway_course = LearnerPathwayCourse.objects.create(course=self.course, step=self.step)

        self.program_course1, self.program_course_run1 = generate_course()
        self.program_course2, self.program_course_run2 = generate_course()
        self.program = ProgramFactory(courses=[self.program_course1, self.program_course2])
        self.learner_pathway_program = LearnerPathwayProgram.objects.create(program=self.program, step=self.step)

    def test_get_estimated_time_of_completion(self):
        """ Verify that `LearnerPathwayStep.get_estimated_time_of_completion` method is working as expected """

        estimated_time_of_completion = self.learner_pathway_course.get_estimated_time_of_completion() + \
            self.learner_pathway_program.get_estimated_time_of_completion()
        assert estimated_time_of_completion == self.step.get_estimated_time_of_completion()

    def test_get_nodes(self):
        """ Verify that `LearnerPathwayStep.get_nodes` method is returning all associated nodes """
        assert self.step.get_nodes() == [self.learner_pathway_course, self.learner_pathway_program]

    def test_get_node(self):
        """ Verify that `LearnerPathwayStep.get_node` method is returning expected object """

        assert self.step.get_node(self.learner_pathway_course.uuid) == self.learner_pathway_course
        assert self.step.get_node(self.learner_pathway_program.uuid) == self.learner_pathway_program

    def test_get_skills(self):
        """ Verify that `LearnerPathwayStep.get_skills` method is aggregating skills as expected """

        expected_skills = [{'name': 'skill name 1', 'description': 'skill description 1'}]

        with mock.patch(
            'course_discovery.apps.learner_pathway.models.get_whitelisted_serialized_skills',
            return_value=expected_skills
        ):
            skills = self.step.get_skills()
            assert skills == expected_skills

    def test_remove_node(self):
        """ verify that `LearnerPathwayStep.remove_node` is correctly deleting object from database """

        course_uuid = self.learner_pathway_course.uuid
        self.step.remove_node(self.learner_pathway_course.uuid)
        assert not LearnerPathwayCourse.objects.filter(uuid=course_uuid).exists()

        program_uuid = self.learner_pathway_program.uuid
        self.step.remove_node(self.learner_pathway_program.uuid)
        assert not LearnerPathwayProgram.objects.filter(uuid=program_uuid).exists()
