import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.models import Course


class CourseFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-id/', suffix='/fake')
    title = FuzzyText(prefix="էҽʂէ çօմɾʂҽ ")

    class Meta:
        model = Course
