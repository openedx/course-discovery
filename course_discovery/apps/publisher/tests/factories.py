from datetime import datetime

import factory
from django.contrib.auth.models import Group
# pylint:disable=ungrouped-imports
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import (
    Course, CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension, OrganizationUserRole, Seat,
    UserAttributes
)


class CourseFactory(factory.DjangoModelFactory):
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")
    number = FuzzyText()
    prerequisites = "prereq 1, prereq 2, prereq 3"
    expected_learnings = "learning 1, learning 2, learning 3"
    syllabus = "week 1:  awesomeness"
    learner_testimonial = "Best course ever!"
    level_type = factory.SubFactory(factories.LevelTypeFactory)

    primary_subject = factory.SubFactory(factories.SubjectFactory)
    secondary_subject = factory.SubFactory(factories.SubjectFactory)
    tertiary_subject = factory.SubFactory(factories.SubjectFactory)
    faq = FuzzyText(prefix='Frequently asked questions')
    video_link = FuzzyText(prefix='http://video.com/çօմɾʂҽ/')

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    enrollment_start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    certificate_generation = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    min_effort = FuzzyInteger(1, 10)
    max_effort = FuzzyInteger(10, 20)
    language = factory.Iterator(LanguageTag.objects.all())
    pacing_type = FuzzyChoice([name for name, __ in CourseRunPacing.choices])
    length = FuzzyInteger(1, 10)
    notes = "Testing notes"
    preview_url = FuzzyText(prefix='https://example.com/')
    contacted_partner_manager = FuzzyChoice((True, False))
    video_language = factory.Iterator(LanguageTag.objects.all())
    short_description_override = FuzzyText()
    title_override = FuzzyText()
    full_description_override = FuzzyText()

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


class GroupFactory(factory.DjangoModelFactory):
    name = FuzzyText(prefix="Test Group ")

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
