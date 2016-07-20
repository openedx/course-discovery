from datetime import datetime
from uuid import uuid4

import factory
from factory.fuzzy import (
    BaseFuzzyAttribute, FuzzyText, FuzzyChoice, FuzzyDateTime, FuzzyInteger, FuzzyDecimal
)
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Organization, Person, Image, Video, Subject, Seat, Prerequisite, LevelType, Program,
    AbstractSocialNetworkModel, CourseRunSocialNetwork, PersonSocialNetwork
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


class FuzzyURL(BaseFuzzyAttribute):
    def fuzz(self):
        protocol = FuzzyChoice(('http', 'https',))
        subdomain = FuzzyText()
        domain = FuzzyText()
        tld = FuzzyChoice(('com', 'net', 'org', 'biz', 'pizza', 'coffee', 'diamonds', 'fail', 'win', 'wtf',))
        resource = FuzzyText()
        return "{protocol}://{subdomain}.{domain}.{tld}/{resource}".format(
            protocol=protocol.fuzz(),
            subdomain=subdomain.fuzz(),
            domain=domain.fuzz(),
            tld=tld.fuzz(),
            resource=resource.fuzz()
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


class SeatFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in Seat.SEAT_TYPE_CHOICES])
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))

    class Meta:
        model = Seat


class CourseFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")
    level_type = factory.SubFactory(LevelTypeFactory)
    image = factory.SubFactory(ImageFactory)
    video = factory.SubFactory(VideoFactory)
    marketing_url = FuzzyText(prefix='https://example.com/test-course-url')

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)
    title_override = None
    short_description_override = None
    full_description_override = None
    language = factory.Iterator(LanguageTag.objects.all())
    start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    enrollment_start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    announcement = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    image = factory.SubFactory(ImageFactory)
    video = factory.SubFactory(VideoFactory)
    min_effort = FuzzyInteger(1, 10)
    max_effort = FuzzyInteger(10, 20)
    pacing_type = FuzzyChoice([name for name, __ in CourseRun.PACING_CHOICES])
    marketing_url = FuzzyText(prefix='https://example.com/test-course-url')

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
    profile_image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Person


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Program

    title = factory.Sequence(lambda n: 'test-program-{}'.format(n))  # pylint: disable=unnecessary-lambda
    uuid = factory.LazyFunction(uuid4)
    subtitle = 'test-subtitle'
    category = 'xseries'
    status = 'unpublished'
    marketing_slug = factory.Sequence(lambda n: 'test-slug-{}'.format(n))  # pylint: disable=unnecessary-lambda


class AbstractSocialNetworkModelFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in AbstractSocialNetworkModel.SOCIAL_NETWORK_CHOICES])
    value = FuzzyText()


class PersonSocialNetworkFactory(AbstractSocialNetworkModelFactory):
    person = factory.SubFactory(PersonFactory)

    class Meta:
        model = PersonSocialNetwork


class CourseRunSocialNetworkFactory(AbstractSocialNetworkModelFactory):
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = CourseRunSocialNetwork
