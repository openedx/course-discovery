from django.test import TestCase

from course_discovery.apps.api.tests.test_utils import make_request
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, ProgramFactory
from course_discovery.apps.learner_pathway.api.serializers import LearnerPathwaySerializer
from course_discovery.apps.learner_pathway.tests.factories import (
    LearnerPathwayCourseFactory, LearnerPathwayFactory, LearnerPathwayProgramFactory, LearnerPathwayStepFactory
)


class TestLearnerPathwaySerializer(TestCase):
    serializer_class = LearnerPathwaySerializer

    def create_pathway(self):
        learner_pathway = LearnerPathwayFactory()
        step = LearnerPathwayStepFactory(pathway=learner_pathway)

        # Create a course in LearnerPathway with a Published course run
        learner_pathway_course = CourseFactory()
        CourseRunFactory(course=learner_pathway_course)
        LearnerPathwayCourseFactory(step=step, course=learner_pathway_course)

        # Create a program in LearnerPathway with a course that has one Published course run
        program_course = CourseFactory()
        CourseRunFactory(course=program_course)
        program = ProgramFactory(courses=[program_course])
        LearnerPathwayProgramFactory(step=step, program=program)
        return learner_pathway

    @classmethod
    def get_expected_data(cls, learner_pathway, request):
        return {
            'id': learner_pathway.id,
            'uuid': str(learner_pathway.uuid),
            'title': learner_pathway.title,
            'status': learner_pathway.status,
            'banner_image': request.build_absolute_uri(learner_pathway.banner_image.url),
            'card_image': request.build_absolute_uri(learner_pathway.card_image.url),
            'overview': learner_pathway.overview,
            'steps': [{
                'uuid': str(step.uuid),
                'min_requirement': step.min_requirement,
                'courses': [
                    {
                        'key': learner_pathway_course.course.key,
                        'title': learner_pathway_course.course.title,
                        'short_description': learner_pathway_course.course.short_description,
                        'card_image_url': learner_pathway_course.course.image_url,
                        'content_type': 'course',
                        'course_runs': [
                            {
                                'key': course_run.key
                            } for course_run in learner_pathway_course.course.course_runs.all()
                        ],
                    } for learner_pathway_course in step.learnerpathwaycourse_set.all()
                ],
                'programs': [
                    {
                        'uuid': str(learner_pathway_program.program.uuid),
                        'title': learner_pathway_program.program.title,
                        'short_description': learner_pathway_program.program.subtitle,
                        'card_image_url': learner_pathway_program.program.card_image_url,
                        'content_type': 'program',
                        'courses': [
                            {
                                'key': course.key,
                                'course_runs': [
                                    {
                                        'key': course_run.key
                                    } for course_run in course.course_runs.all()
                                ]
                            } for course in learner_pathway_program.program.courses.all()
                        ],
                    } for learner_pathway_program in step.learnerpathwayprogram_set.all()
                ]
            } for step in learner_pathway.steps.all()],
        }

    def test_data(self):
        request = make_request()
        pathway = self.create_pathway()
        serializer = self.serializer_class(pathway, context={'request': request})
        expected = self.get_expected_data(pathway, request)
        self.assertDictEqual(serializer.data, expected)
