from datetime import datetime

import factory
from django.contrib.auth.models import Group
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import (
    Course, CourseEntitlement, CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension,
    OrganizationUserRole, Seat, UserAttributes
)


class CourseFactory(factory.DjangoModelFactory):
    title = FuzzyText()
    number = FuzzyText()
    version = Course.SEAT_VERSION

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    pacing_type = FuzzyChoice(CourseRunPacing.values.keys())

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
