from datetime import datetime

import factory
from django.contrib.auth.models import Group
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import UserFactory, add_m2m_data
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import (
    Course, CourseEntitlement, CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension,
    OrganizationUserRole, Seat, UserAttributes
)


class CourseFactory(factory.DjangoModelFactory):
    title = FuzzyText()
    short_description = FuzzyText()
    full_description = FuzzyText()
    number = FuzzyText()
    prerequisites = FuzzyText()
    expected_learnings = FuzzyText()
    syllabus = FuzzyText()
    learner_testimonial = FuzzyText()
    level_type = factory.SubFactory(factories.LevelTypeFactory)
    image = factory.django.ImageField()
    version = Course.SEAT_VERSION

    primary_subject = factory.SubFactory(factories.SubjectFactory)
    secondary_subject = factory.SubFactory(factories.SubjectFactory)
    tertiary_subject = factory.SubFactory(factories.SubjectFactory)
    faq = FuzzyText()
    video_link = factory.Faker('url')

    @factory.post_generation
    def organizations(self, create, extracted, **kwargs):  # pylint: disable=unused-argument
        if create:
            add_m2m_data(self.organizations, extracted)

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    certificate_generation = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    is_micromasters = False
    micromasters_name = ""
    min_effort = FuzzyInteger(1, 10)
    max_effort = FuzzyInteger(10, 20)
    language = factory.Iterator(LanguageTag.objects.all())
    pacing_type = FuzzyChoice(CourseRunPacing.values.keys())
    length = FuzzyInteger(1, 10)
    notes = FuzzyText()
    contacted_partner_manager = FuzzyChoice((True, False))
    video_language = factory.Iterator(LanguageTag.objects.all())
    short_description_override = FuzzyText()
    title_override = FuzzyText()
    full_description_override = FuzzyText()
    external_key = None

    @factory.post_generation
    def staff(self, create, extracted, **kwargs):  # pylint: disable=unused-argument
        if create:
            add_m2m_data(self.staff, extracted)

    @factory.post_generation
    def transcript_languages(self, create, extracted, **kwargs):  # pylint: disable=unused-argument
        if create:
            add_m2m_data(self.transcript_languages, extracted)

    class Meta:
        model = CourseRun


class SeatFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in Seat.SEAT_TYPE_CHOICES])
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    course_run = factory.SubFactory(CourseRunFactory)
    credit_price = FuzzyDecimal(0.0, 650.0)

    class Meta:
        model = Seat


class CourseEntitlementFactory(factory.DjangoModelFactory):
    mode = FuzzyChoice([name for name, __ in CourseEntitlement.COURSE_MODE_CHOICES])
    price = FuzzyDecimal(1.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    course = factory.SubFactory(CourseFactory)

    class Meta:
        model = CourseEntitlement


class GroupFactory(factory.DjangoModelFactory):
    name = FuzzyText()

    class Meta:
        model = Group


class UserAttributeFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = UserAttributes


class OrganizationUserRoleFactory(factory.DjangoModelFactory):
    organization = factory.SubFactory(factories.OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = FuzzyChoice(PublisherUserRole.values.keys())

    class Meta:
        model = OrganizationUserRole


class CourseUserRoleFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    user = factory.SubFactory(UserFactory)
    role = FuzzyChoice(PublisherUserRole.values.keys())

    class Meta:
        model = CourseUserRole


class OrganizationExtensionFactory(factory.DjangoModelFactory):
    organization = factory.SubFactory(factories.OrganizationFactory)
    group = factory.SubFactory(GroupFactory)

    class Meta:
        model = OrganizationExtension


class CourseStateFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    owner_role = FuzzyChoice(PublisherUserRole.values.keys())

    class Meta:
        model = CourseState


class CourseRunStateFactory(factory.DjangoModelFactory):
    course_run = factory.SubFactory(CourseRunFactory)
    owner_role = FuzzyChoice(PublisherUserRole.values.keys())

    class Meta:
        model = CourseRunState
