from django.test import TestCase

from course_discovery.apps.api.tests.test_utils import make_request
from course_discovery.apps.learner_pathway.api.serializers import LearnerPathwaySerializer
from course_discovery.apps.learner_pathway.tests.factories import (
    LearnerPathwayCourseFactory, LearnerPathwayFactory, LearnerPathwayProgramFactory, LearnerPathwayStepFactory
)


class TestLearnerPathwaySerializer(TestCase):
    serializer_class = LearnerPathwaySerializer

    def create_pathway(self):
        learner_pathway = LearnerPathwayFactory()
        step = LearnerPathwayStepFactory(pathway=learner_pathway)
        LearnerPathwayCourseFactory(step=step)
        LearnerPathwayProgramFactory(step=step)
        return learner_pathway

    @classmethod
    def get_expected_data(cls, learner_pathway, request):
        return {
            'id': learner_pathway.id,
            'uuid': str(learner_pathway.uuid),
            'title': learner_pathway.title,
            'status': learner_pathway.status,
            'banner_image': request.build_absolute_uri(learner_pathway.banner_image.url),
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
                    } for learner_pathway_course in step.learnerpathwaycourse_set.all()
                ],
                'programs': [
                    {
                        'uuid': str(learner_pathway_program.program.uuid),
                        'title': learner_pathway_program.program.title,
                        'short_description': learner_pathway_program.program.subtitle,
                        'card_image_url': learner_pathway_program.program.card_image_url,
                        'content_type': 'program'
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
