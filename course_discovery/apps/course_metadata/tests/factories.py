import datetime

import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.models import(
    Course, CourseRun, Organization, Person, Image, Video, Subject, Prerequisite, LevelType
)


class TimestampModelFactory(factory.DjangoModelFactory):
    created = datetime.datetime.now()
    modified = created


class AbstractMediaModelFactory(factory.DjangoModelFactory):
    src = FuzzyText()
    description = FuzzyText()


class AbstractNamedModelFactory(factory.DjangoModelFactory):
    name = FuzzyText()


class ImageFactory(AbstractMediaModelFactory):
    height = 100
    width = 100

    class Meta:
        model = Image


class VideoFactory(AbstractMediaModelFactory):
    image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Video


class SubjectFactory(AbstractNamedModelFactory):

    class Meta:
        model = Subject


class LevelTypeFactory(AbstractNamedModelFactory):

    class Meta:
        model = LevelType


class PrerequisiteFactory(AbstractNamedModelFactory):

    class Meta:
        model = Prerequisite


class CourseFactory(TimestampModelFactory):
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")
    level_type = factory.SubFactory(LevelTypeFactory)
    image = factory.SubFactory(ImageFactory)
    video = factory.SubFactory(VideoFactory)

    class Meta:
        model = Course


class CourseRunFactory(TimestampModelFactory):
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)
    title_override = None
    short_description_override = None
    full_description_override = None

    class Meta:
        model = CourseRun


class OrganizationFactory(TimestampModelFactory):
    key = FuzzyText(prefix='Org.fake/')
    name = FuzzyText()
    description = FuzzyText()
    homepage_url = FuzzyText()
    logo_image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Organization


class PersonFactory(TimestampModelFactory):
    key = FuzzyText(prefix='Person.fake/')
    name = FuzzyText()
    title = FuzzyText()
    bio = FuzzyText()

    class Meta:
        model = Person
