import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization, Person


class CourseFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)
    title_override = None
    short_description_override = None
    full_description_override = None

    class Meta:
        model = CourseRun


class OrganizationFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='Org.fake/')
    name = FuzzyText()

    class Meta:
        model = Organization


class PersonFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='Person.fake/')
    name = FuzzyText()
    title = FuzzyText()
    bio = FuzzyText()

    class Meta:
        model = Person
