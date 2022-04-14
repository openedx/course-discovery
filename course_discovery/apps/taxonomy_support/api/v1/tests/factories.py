import factory
from factory.fuzzy import FuzzyDecimal, FuzzyInteger

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.taxonomy_support.models import CourseRecommendation


class CourseRecommendationFactory(factory.django.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    recommended_course = factory.SubFactory(CourseFactory)
    skills_intersection_ratio = FuzzyDecimal(0.01, 1.0)
    skills_intersection_length = FuzzyInteger(1, 10)
    subjects_intersection_ratio = FuzzyDecimal(0.01, 1.0)
    subjects_intersection_length = FuzzyInteger(1, 10)

    class Meta:
        model = CourseRecommendation
