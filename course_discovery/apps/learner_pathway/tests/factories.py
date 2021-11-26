import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.learner_pathway.models import LearnerPathway, LearnerPathwayStep


class LearnerPathwayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathway

    name = FuzzyText(prefix='learner-pathway-name-')
    uuid = factory.Faker('uuid4')


class LearnerPathwayStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearnerPathwayStep

    uuid = factory.Faker('uuid4')
    pathway = factory.SubFactory(LearnerPathwayFactory)
