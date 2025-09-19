from datetime import datetime

import factory
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.tests.factories import PartnerFactory, add_m2m_data
from course_discovery.apps.core.tests.utils import FuzzyURL
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=unused-argument


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


class SubjectFactory(factory.DjangoModelFactory):
    class Meta:
        model = Subject

    name = FuzzyText()
    description = FuzzyText()
    banner_image_url = FuzzyURL()
    card_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class TopicFactory(factory.DjangoModelFactory):
    class Meta:
        model = Topic

    name = FuzzyText()
    description = FuzzyText()
    long_description = FuzzyText()
    banner_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class LevelTypeFactory(AbstractNamedModelFactory):
    class Meta:
        model = LevelType


class PrerequisiteFactory(AbstractNamedModelFactory):
    class Meta:
        model = Prerequisite


class CourseFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    card_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    status = CourseRunStatus.Published
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)
    title_override = None
    start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    enrollment_start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC)).end_dt

    class Meta:
        model = CourseRun


class SeatFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in Seat.SEAT_TYPE_CHOICES])
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    sku = FuzzyText(length=8)
    bulk_sku = FuzzyText(length=8)
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = Seat


class OrganizationFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText()
    name = FuzzyText()
    description = FuzzyText()
    homepage_url = FuzzyURL()
    logo_image_url = FuzzyURL()
    banner_image_url = FuzzyURL()
    certificate_logo_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    marketing_url_path = FuzzyText()

    class Meta:
        model = Organization


class PersonFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    partner = factory.SubFactory(PartnerFactory)
    given_name = factory.Faker('first_name')
    family_name = factory.Faker('last_name')
    bio = FuzzyText()
    profile_image_url = FuzzyURL()
    profile_image = FuzzyText(prefix='https://example.com/person/profile_image')

    class Meta:
        model = Person


class PositionFactory(factory.DjangoModelFactory):
    person = factory.SubFactory(PersonFactory)
    title = FuzzyText()
    organization = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Position


class ProgramTypeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = ProgramType

    name = FuzzyText()
    logo_image = FuzzyText(prefix='https://example.com/program/logo')

    @factory.post_generation
    def applicable_seat_types(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.applicable_seat_types, extracted)


class EndorsementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Endorsement

    endorser = factory.SubFactory(PersonFactory)
    quote = FuzzyText()


class CorporateEndorsementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = CorporateEndorsement

    corporation_name = FuzzyText()
    statement = FuzzyText()
    image = factory.SubFactory(ImageFactory)

    @factory.post_generation
    def individual_endorsements(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.individual_endorsements, extracted)


class JobOutlookItemFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = JobOutlookItem

    value = FuzzyText()


class FAQFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = FAQ

    question = FuzzyText()
    answer = FuzzyText()


class ExpectedLearningItemFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = ExpectedLearningItem

    value = FuzzyText()


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Program

    title = factory.Sequence(lambda n: 'test-program-{}'.format(n))  # pylint: disable=unnecessary-lambda
    uuid = factory.LazyFunction(uuid4)
    status = ProgramStatus.Active
    card_image_url = FuzzyText(prefix='https://example.com/program/card')
    partner = factory.SubFactory(PartnerFactory)

    @factory.post_generation
    def courses(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.courses, extracted)


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


class SeatTypeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = SeatType

    name = FuzzyText()


class SyllabusItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SyllabusItem


class PersonWorkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PersonWork

    person = factory.SubFactory(PersonFactory)
