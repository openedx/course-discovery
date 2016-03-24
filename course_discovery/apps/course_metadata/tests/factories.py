import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.models import Course, CourseRun


class CourseFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-id/', suffix='/fake')
    name = FuzzyText(prefix="էҽʂէ çօմɾʂҽ ")

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)

    class Meta:
        model = CourseRun
