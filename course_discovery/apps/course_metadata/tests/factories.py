import factory
from factory.fuzzy import BaseFuzzyAttribute, FuzzyText, FuzzyChoice

from course_discovery.apps.course_metadata.models import(
    Course, CourseRun, Organization, Person, Image, Video, Subject, Prerequisite, LevelType
)


class FuzzyURL(BaseFuzzyAttribute):
    def fuzz(self):
        protocol = FuzzyChoice(('http', 'https',))
        subdomain = FuzzyText()
        domain = FuzzyText()
        tld = FuzzyChoice(('com', 'net', 'org', 'biz', 'pizza', 'coffee', 'diamonds', 'fail', 'win', 'wtf',))
        resource = FuzzyText()
        return "{protocol}://{subdomain}.{domain}.{tld}/{resource}".format(
            protocol=protocol,
            subdomain=subdomain,
            domain=domain,
            tld=tld,
            resource=resource
        )


class AbstractMediaModelFactory(factory.DjangoModelFactory):
    src = FuzzyURL()
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


class CourseFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")
    level_type = factory.SubFactory(LevelTypeFactory)
    image = factory.SubFactory(ImageFactory)
    video = factory.SubFactory(VideoFactory)

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
    description = FuzzyText()
    homepage_url = FuzzyURL()
    logo_image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Organization


class PersonFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='Person.fake/')
    name = FuzzyText()
    title = FuzzyText()
    bio = FuzzyText()

    class Meta:
        model = Person
