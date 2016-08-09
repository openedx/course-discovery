from datetime import datetime
from uuid import uuid4

import factory
from factory.fuzzy import (
    FuzzyText, FuzzyChoice, FuzzyDateTime, FuzzyInteger, FuzzyDecimal
)
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.utils import FuzzyURL
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Organization, Person, Image, Video, Subject, Seat, Prerequisite, LevelType, Program,
    AbstractSocialNetworkModel, CourseRunSocialNetwork, PersonSocialNetwork, ProgramType, SeatType,
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=no-member, unused-argument

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
    partner = factory.SubFactory(PartnerFactory)

    class Meta:
        model = Course

    @factory.post_generation
    def subjects(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            for subject in extracted:
                self.subjects.add(subject)


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

    @factory.post_generation
    def transcript_languages(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            for transcript_language in extracted:
                self.transcript_languages.add(transcript_language)


class OrganizationFactory(factory.DjangoModelFactory):
    key = FuzzyText(prefix='Org.fake/')
    name = FuzzyText()
    description = FuzzyText()
    homepage_url = FuzzyURL()
    logo_image = factory.SubFactory(ImageFactory)
    partner = factory.SubFactory(PartnerFactory)

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


class ProgramTypeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = ProgramType

    name = FuzzyText()

    @factory.post_generation
    def applicable_seat_types(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            for seat_type in extracted:
                self.applicable_seat_types.add(seat_type)


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Program

    title = factory.Sequence(lambda n: 'test-program-{}'.format(n))  # pylint: disable=unnecessary-lambda
    uuid = factory.LazyFunction(uuid4)
    subtitle = 'test-subtitle'
    type = factory.SubFactory(ProgramTypeFactory)
    status = Program.ProgramStatus.Unpublished
    marketing_slug = factory.Sequence(lambda n: 'test-slug-{}'.format(n))  # pylint: disable=unnecessary-lambda
    banner_image_url = FuzzyText(prefix='https://example.com/program/banner')
    card_image_url = FuzzyText(prefix='https://example.com/program/card')
    partner = factory.SubFactory(PartnerFactory)

    @factory.post_generation
    def courses(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            # Use the passed in list of courses
            for course in extracted:
                self.courses.add(course)

    @factory.post_generation
    def excluded_course_runs(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            for course_run in extracted:
                self.excluded_course_runs.add(course_run)

    @factory.post_generation
    def authoring_organizations(self, create, extracted, **kwargs):
        if not create:  # pragma: no cover
            # Simple build, do nothing.
            return

        if extracted:
            for organization in extracted:
                self.authoring_organizations.add(organization)


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
