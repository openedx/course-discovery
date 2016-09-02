from datetime import datetime

import factory
from django.contrib.auth.models import Group
from factory.fuzzy import FuzzyText, FuzzyChoice, FuzzyDecimal, FuzzyDateTime, FuzzyInteger
from pytz import UTC

from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.course_metadata.models import CourseRun as CourseMetadataCourseRun
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, State


class StateFactory(factory.DjangoModelFactory):

    class Meta:
        model = State


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

    class Meta:
        model = Course


class CourseRunFactory(factory.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    state = factory.SubFactory(StateFactory)
    start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    enrollment_start = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    certificate_generation = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    min_effort = FuzzyInteger(1, 10)
    max_effort = FuzzyInteger(10, 20)
    language = factory.Iterator(LanguageTag.objects.all())
    pacing_type = FuzzyChoice([name for name, __ in CourseMetadataCourseRun.Pacing.choices])
    length = FuzzyInteger(1, 10)
    seo_review = "test-seo-review"
    keywords = "Test1, Test2, Test3"
    notes = "Testing notes"

    class Meta:
        model = CourseRun


class SeatFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in Seat.SEAT_TYPE_CHOICES])
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime(2014, 1, 1, tzinfo=UTC))
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = Seat


class GroupFactory(factory.DjangoModelFactory):

    class Meta:
        model = Group
