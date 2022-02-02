import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.tests.factories import CourseFactory, ProgramFactory
from course_discovery.apps.learner_pathway.models import (
    LearnerPathway, LearnerPathwayCourse, LearnerPathwayProgram, LearnerPathwayStep
)


class LearnerPathwayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathway

    name = FuzzyText(prefix='learner-pathway-name-')
    uuid = factory.Faker('uuid4')
    banner_image = factory.django.ImageField()
    overview = FuzzyText(prefix='learner-pathway-overview-')


class LearnerPathwayStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathwayStep

    uuid = factory.Faker('uuid4')
    pathway = factory.SubFactory(LearnerPathwayFactory)


class LearnerPathwayCourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathwayCourse

    uuid = factory.Faker('uuid4')
    step = factory.SubFactory(LearnerPathwayStepFactory)
    course = factory.SubFactory(CourseFactory)


class LearnerPathwayProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathwayProgram

    uuid = factory.Faker('uuid4')
    step = factory.SubFactory(LearnerPathwayStepFactory)
    program = factory.SubFactory(ProgramFactory)
