import itertools
import datetime
from decimal import Decimal

import ddt
import mock
import responses
from dateutil.parser import parse
import pytz
from django.conf import settings
from django.db import IntegrityError
from django.db.models.functions import Lower
from django.test import TestCase
from factory.fuzzy import FuzzyText
from freezegun import freeze_time

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import (
    FAQ, AbstractMediaModel, AbstractNamedModel, AbstractValueModel, CorporateEndorsement, Course, CourseRun,
    CourseRunStatus, Endorsement, ProgramType, Seat, SeatType
)
from course_discovery.apps.course_metadata.publishers import MarketingSitePublisher
from course_discovery.apps.course_metadata.tests import factories, toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ImageFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=no-member


class CourseTests(ElasticsearchTestMixin, TestCase):
    """ Tests for the `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        self.assertEqual(str(self.course), '{key}: {title}'.format(key=self.course.key, title=self.course.title))

    def test_search(self):
        """ Verify the method returns a filtered queryset of courses. """
        title = 'Some random title'
        courses = factories.CourseFactory.create_batch(3, title=title)
        # Sort lowercase keys to prevent different sort orders due to casing.
        # For example, sorted(['a', 'Z']) gives ['Z', 'a'], but an ordered
        # queryset containing the same values may give ['a', 'Z'] depending
        # on the database backend in use.
        courses = sorted(courses, key=lambda course: course.key.lower())

        query = 'title:' + title
        # Use Lower() to force a case-insensitive sort.
        actual = list(Course.search(query).order_by(Lower('key')))

        self.assertEqual(actual, courses)

    def test_course_run_update_caught_exception(self):
        """ Test that the index update process failing will not cause the course save to error """
        with mock.patch.object(Course, 'reindex_course_runs', side_effect=Exception):
            self.course.save()


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the `CourseRun` model. """

    def setUp(self):
        super(CourseRunTests, self).setUp()
        self.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        course_run = self.course_run
        self.assertEqual(str(course_run), '{key}: {title}'.format(key=course_run.key, title=course_run.title))

    @ddt.data('title', 'short_description', 'full_description')
    def test_override_fields(self, field_name):
        """ Verify the `CourseRun`'s override field overrides the related `Course`'s field. """
        override_field_name = "{}_override".format(field_name)
        self.assertIsNone(getattr(self.course_run, override_field_name))
        self.assertEqual(getattr(self.course_run, field_name), getattr(self.course_run.course, field_name))

        # Setting the property to a non-empty value should set the override field,
        # and trigger the field property getter to use the override.
        override_text = 'A Better World'
        setattr(self.course_run, field_name, override_text)
        self.assertEqual(getattr(self.course_run, override_field_name), override_text)
        self.assertEqual(getattr(self.course_run, field_name), override_text)

        # Setting the title property to an empty value should set the title_override field to None,
        # and trigger the title property getter to use the title of the parent course.
        setattr(self.course_run, field_name, None)
        self.assertIsNone(getattr(self.course_run, override_field_name))
        self.assertEqual(getattr(self.course_run, field_name), getattr(self.course_run.course, field_name))

    def test_search(self):
        """ Verify the method returns a filtered queryset of course runs. """
        title = 'Some random title'
        course_runs = factories.CourseRunFactory.create_batch(3, title=title)
        query = 'title:' + title
        actual_sorted = sorted(SearchQuerySetWrapper(CourseRun.search(query)), key=lambda course_run: course_run.key)
        expected_sorted = sorted(course_runs, key=lambda course_run: course_run.key)
        self.assertEqual(actual_sorted, expected_sorted)

    def test_seat_types(self):
        """ Verify the property returns a list of all seat types associated with the course run. """
        self.assertEqual(self.course_run.seat_types, [])

        seats = factories.SeatFactory.create_batch(3, course_run=self.course_run)
        expected = sorted([seat.type for seat in seats])
        self.assertEqual(sorted(self.course_run.seat_types), expected)

    @ddt.data(
        ('obviously-wrong', None,),
        (('audit',), 'audit',),
        (('honor',), 'honor',),
        (('credit', 'verified', 'audit',), 'credit',),
        (('verified', 'honor',), 'verified',),
        (('professional',), 'professional',),
        (('no-id-professional',), 'professional',),
    )
    @ddt.unpack
    def test_type(self, seat_types, expected_course_run_type):
        """ Verify the property returns the appropriate type string for the CourseRun. """
        for seat_type in seat_types:
            factories.SeatFactory(course_run=self.course_run, type=seat_type)
        self.assertEqual(self.course_run.type, expected_course_run_type)

    def test_level_type(self):
        """ Verify the property returns the associated Course's level type. """
        self.assertEqual(self.course_run.level_type, self.course_run.course.level_type)

    @freeze_time('2016-06-21 00:00:00Z')
    @ddt.data(
        (None, None, 'Upcoming'),
        ('2030-01-01 00:00:00Z', None, 'Upcoming'),
        (None, '2016-01-01 00:00:00Z', 'Archived'),
        ('2015-01-01 00:00:00Z', '2016-01-01 00:00:00Z', 'Archived'),
        ('2016-01-01 00:00:00Z', '2017-01-01 00:00:00Z', 'Current'),
        ('2016-07-21 00:00:00Z', '2017-01-01 00:00:00Z', 'Starting Soon'),
    )
    @ddt.unpack
    def test_availability(self, start, end, expected_availability):
        """ Verify the property returns the appropriate availability string based on the start/end dates. """
        if start:
            start = parse(start)

        if end:
            end = parse(end)
        course_run = factories.CourseRunFactory(start=start, end=end)
        self.assertEqual(course_run.availability, expected_availability)

    def test_marketing_url(self):
        """ Verify the property constructs a marketing URL based on the marketing slug. """
        expected = '{root}/course/{slug}'.format(root=self.course_run.course.partner.marketing_site_url_root.strip('/'),
                                                 slug=self.course_run.slug)
        self.assertEqual(self.course_run.marketing_url, expected)

    @ddt.data(None, '')
    def test_marketing_url_with_empty_marketing_slug(self, slug):
        """ Verify the property returns None if the CourseRun has no marketing_slug value. """
        course_run = CourseRunFactory(slug=slug)
        self.assertIsNone(course_run.marketing_url)

    def test_program_types(self):
        """ Verify the property retrieves program types correctly based on programs. """
        courses = [self.course_run.course]
        program = factories.ProgramFactory(courses=courses)
        other_program = factories.ProgramFactory(courses=courses)
        self.assertCountEqual(self.course_run.program_types, [program.type.name, other_program.type.name])

    def test_unpublished_program_types(self):
        """ Verify the property exludes program types that are unpublished. """
        courses = [self.course_run.course]
        program = factories.ProgramFactory(courses=courses)
        factories.ProgramFactory(courses=courses, status=ProgramStatus.Unpublished)
        self.assertEqual(self.course_run.program_types, [program.type.name])

    def test_exclude_deleted_program_types(self):
        """ Verify the program types property exclude programs that are deleted """
        active_program = factories.ProgramFactory(courses=[self.course_run.course])
        factories.ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)
        self.assertEqual(self.course_run.program_types, [active_program.type.name])


    @ddt.data(
        # Case 1: Should be True when CourseRun is published, not hidden, and has Seats.
        (True, False, True, True),

        # Case 2: Should be False when CourseRun is hidden.
        (True, True, True, False),

        # Case 3: Should be False when CourseRun doesn't have any Seats.
        (True, False, False, False),

        # Case 4: Should be False when CourseRun is not published.
        (False, False, True, False),
    )
    @ddt.unpack
    def test_is_publicly_visible(self, is_published, is_hidden, has_seats, expected_result):
        """
        Verify that is_publicly_visible returns True for CourseRuns that have Seats, are published, and are not
        hidden.
        """
        status = CourseRunStatus.Published if is_published else CourseRunStatus.Unpublished
        course_run = factories.CourseRunFactory.create(status=status, hidden=is_hidden)
        if has_seats:
            factories.SeatFactory.create(course_run=course_run)

        assert expected_result == course_run.is_publicly_visible


    @ddt.data(
        # Case 1: Should be True when enrollment_start is unspecified or in the past and
        # enrollment_end is unspecified or in the future.
        (None, None, True),
        (None, datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), True),
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1), None, True),
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1),
            datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), True),

        # Case 2: Should be False when enrollment_start is in the future or enrollment_end is in the past.
        (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), None, False),
        (None, datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1), False),
    )
    @ddt.unpack
    def test_is_enrollable(self, enrollment_start, enrollment_end, expected_result):
        """ Verify that is_enrollable is True when enrollment has begun and has not ended."""
        course_run = factories.CourseRunFactory.create(
            enrollment_start=enrollment_start,
            enrollment_end=enrollment_end
        )
        assert expected_result == course_run.is_enrollable

    @ddt.data(
        # Case 1: Should be True if enrollment_start is in future.
        (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), True),

        # Case 2: Should be False if enrollment_start is unspecified or in the past.
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1), False),
        (None, False)
    )
    @ddt.unpack
    def test_will_be_enrollable(self, enrollment_start, expected_result):
        """ Verify that will_be_enrollable is True when enrollment will begin in the future."""
        course_run = factories.CourseRunFactory.create(enrollment_start=enrollment_start, enrollment_end=None)
        assert expected_result == course_run.will_be_enrollable

    @ddt.data(
        # Case 1: Should be True if start is unspecified or in the past.
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1), True),
        (None, True),

        # Case 2: Should be False if start is in the future.
        (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), False),
    )
    @ddt.unpack
    def test_is_consumable(self, start, expected_result):
        """
        Verify that is_consumable is True when start is unspecifed or in the future.
        """
        course_run = factories.CourseRunFactory.create(start=start, end=None)
        assert expected_result == course_run.is_consumable

    @ddt.data(
        # Case 1: Should be True if course has_enrollable_paid_seats and paid_seat_enrollment_end is unspecified
        # or in the future.
        (True, None, True),
        (True, datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), True),

        # Case 2: Should be False if course does not have paid seats.
        (False, datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1), False),

        # Case 3: Should be False if paid_seat_enrollment_end is in the past.
        (True, datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1), False),
    )
    @ddt.unpack
    def test_is_or_will_be_purchasable(self, has_enrollable_paid_seats, paid_seat_enrollment_end, expected_result):
        """
        Verify that is_or_will_be_purchasable is True when the CourseRun has enrollable paid seats and the paid
        seat enrollment end is unspecified or in the past.
        """
        with mock.patch.object(CourseRun, 'has_enrollable_paid_seats', return_value=has_enrollable_paid_seats):
            with mock.patch.object(CourseRun, 'get_paid_seat_enrollment_end', return_value=paid_seat_enrollment_end):
                course_run = factories.CourseRunFactory.create()
                assert expected_result == course_run.is_or_will_be_purchasable

    @ddt.data(
        # Case 1: Return False when there are no paid Seats.
        ([('audit', 0)], False),
        ([('audit', 0), ('verified', 0)], False),

        # Case 2: Return False when there are no paid Seats without prerequisites.
        ([(seat_type, 1) for seat_type in Seat.SEATS_WITH_PREREQUISITES], False),

        # Case 3: Return True when there is at least one paid Seat without prerequisites.
        ([('audit', 0), ('verified', 1)], True),
        ([('audit', 0), ('verified', 1), ('professional', 1)], True),
        ([('audit', 0), ('verified', 1)] + [(seat_type, 1) for seat_type in Seat.SEATS_WITH_PREREQUISITES], True),
    )
    @ddt.unpack
    def test_has_enrollable_paid_seats(self, seat_config, expected_result):
        """
        Verify that has_enrollable_paid_seats is True when CourseRun has Seats with price > 0 and no prerequisites.
        """
        course_run = factories.CourseRunFactory.create()
        for seat_type, price in seat_config:
            factories.SeatFactory.create(course_run=course_run, type=seat_type, price=price)
        self.assertEqual(course_run.has_enrollable_paid_seats(), expected_result)

    @ddt.data(
        # Case 1: Return None when there are no enrollable paid Seats.
        ([('audit', 0, None)], '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', None),
        ([(seat_type, 1, None) for seat_type in Seat.SEATS_WITH_PREREQUISITES],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', None),

        # Case 2: Return the latest upgrade_deadline of the enrollable paid Seats when it's earlier than
        # enrollment_end and course end.
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z')],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', '2016-07-30 00:00:00Z'),
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, '2016-08-15 00:00:00Z')],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', '2016-08-15 00:00:00Z'),
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z')] +
         [(seat_type, 1, '2016-08-15 00:00:00Z') for seat_type in Seat.SEATS_WITH_PREREQUISITES],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', '2016-07-30 00:00:00Z'),

        # Case 3: Return enrollment_end when it's earlier than course end and the latest upgrade_deadline of the
        # enrollable paid Seats, or when one of those Seats does not have an upgrade_deadline.
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, '2016-09-15 00:00:00Z')],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', '2016-08-31 00:00:00Z'),
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, None)],
         '2016-12-31 00:00:00Z', '2016-08-31 00:00:00Z', '2016-08-31 00:00:00Z'),

        # Case 4: Return course end when it's earlier than enrollment_end or enrollment_end is None, and it's earlier
        # than the latest upgrade_deadline of the enrollable paid Seats or when one of those Seats does not have an
        # upgrade_deadline.
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, '2017-09-15 00:00:00Z')],
         '2016-12-31 00:00:00Z', '2017-08-31 00:00:00Z', '2016-12-31 00:00:00Z'),
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, None)],
         '2016-12-31 00:00:00Z', '2017-12-31 00:00:00Z', '2016-12-31 00:00:00Z'),
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, None)],
         '2016-12-31 00:00:00Z', None, '2016-12-31 00:00:00Z'),

        # Case 5: Return None when course end and enrollment_end are None and there's an enrollable paid Seat without
        # an upgrade_deadline, even when there's another enrollable paid Seat with an upgrade_deadline.
        ([('audit', 0, None), ('verified', 1, '2016-07-30 00:00:00Z'), ('professional', 1, None)],
         None, None, None)
    )
    @ddt.unpack
    def test_get_paid_seat_enrollment_end(self, seat_config, course_end, course_enrollment_end, expected_result):
        """
        Verify that paid_seat_enrollment_end returns the latest possible date for which an unerolled user may
        enroll and purchase an upgrade for the CourseRun or None if date unknown or paid Seats are not available.
        """
        end = parse(course_end) if course_end else None
        enrollment_end = parse(course_enrollment_end) if course_enrollment_end else None
        course_run = factories.CourseRunFactory.create(end=end, enrollment_end=enrollment_end)
        for seat_type, price, deadline in seat_config:
            deadline = parse(deadline) if deadline else None
            factories.SeatFactory.create(course_run=course_run, type=seat_type, price=price, upgrade_deadline=deadline)

        expected_result = parse(expected_result) if expected_result else None
        self.assertEqual(course_run.get_paid_seat_enrollment_end(), expected_result)


class OrganizationTests(TestCase):
    """ Tests for the `Organization` model. """

    def setUp(self):
        super(OrganizationTests, self).setUp()
        self.organization = factories.OrganizationFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and name. """
        self.assertEqual(str(self.organization), '{key}: {name}'.format(key=self.organization.key,
                                                                        name=self.organization.name))

    def test_marketing_url(self):
        """ Verify the property creates a complete marketing URL. """
        expected = '{root}/{slug}'.format(root=self.organization.partner.marketing_site_url_root.strip('/'),
                                          slug=self.organization.marketing_url_path)
        self.assertEqual(self.organization.marketing_url, expected)

    def test_marketing_url_without_marketing_url_path(self):
        """ Verify the property returns None if the Organization has no marketing_url_path set. """
        self.organization.marketing_url_path = ''
        self.assertIsNone(self.organization.marketing_url)


class PersonTests(TestCase):
    """ Tests for the `Person` model. """

    def setUp(self):
        super(PersonTests, self).setUp()
        self.person = factories.PersonFactory()

    def test_full_name(self):
        """ Verify the property returns the person's full name. """
        expected = self.person.given_name + ' ' + self.person.family_name
        self.assertEqual(self.person.full_name, expected)

    def test_get_profile_image_url(self):
        """
        Verify that property returns profile_image_url if profile_image_url
        exists other wise it returns uploaded image url.
        """
        self.assertEqual(self.person.get_profile_image_url, self.person.profile_image_url)

        # create another person with out profile_image_url
        person = factories.PersonFactory(profile_image_url=None)
        self.assertEqual(person.get_profile_image_url, person.profile_image.url)

        # create another person with out profile_image_url and profile_image
        person = factories.PersonFactory(profile_image_url=None, profile_image=None)
        self.assertFalse(person.get_profile_image_url)

    def test_str(self):
        """ Verify casting an instance to a string returns the person's full name. """
        self.assertEqual(str(self.person), self.person.full_name)


class PositionTests(TestCase):
    """ Tests for the `Position` model. """

    def setUp(self):
        super(PositionTests, self).setUp()
        self.position = factories.PositionFactory()

    def test_organization_name(self):
        """ Verify the property returns the name of the related Organization or the overridden value. """
        self.assertEqual(self.position.organization_name, self.position.organization.name)

        self.position.organization_override = 'ACME'
        self.assertEqual(self.position.organization_name, self.position.organization_override)

    def test_str(self):
        """ Verify casting an instance to a string returns the title and organization. """
        expected = self.position.title + ' at ' + self.position.organization_name
        self.assertEqual(str(self.position), expected)


class AbstractNamedModelTests(TestCase):
    """ Tests for AbstractNamedModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the name. """

        class TestAbstractNamedModel(AbstractNamedModel):
            pass

        name = 'abc'
        instance = TestAbstractNamedModel(name=name)
        self.assertEqual(str(instance), name)


class AbstractMediaModelTests(TestCase):
    """ Tests for AbstractMediaModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the src. """

        class TestAbstractMediaModel(AbstractMediaModel):
            pass

        src = 'http://example.com/image.jpg'
        instance = TestAbstractMediaModel(src=src)
        self.assertEqual(str(instance), src)


class AbstractValueModelTests(TestCase):
    """ Tests for AbstractValueModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the value. """

        class TestAbstractValueModel(AbstractValueModel):
            pass

        value = 'abc'
        instance = TestAbstractValueModel(value=value)
        self.assertEqual(str(instance), value)


@ddt.ddt
class ProgramTests(MarketingSitePublisherTestMixin):
    """Tests of the Program model."""

    def setUp(self):
        super(ProgramTests, self).setUp()
        transcript_languages = LanguageTag.objects.all()[:2]
        subjects = factories.SubjectFactory.create_batch(2)
        self.course_runs = factories.CourseRunFactory.create_batch(
            3, transcript_languages=transcript_languages, course__subjects=subjects)
        self.courses = [course_run.course for course_run in self.course_runs]
        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(courses=self.courses, excluded_course_runs=[self.excluded_course_run])

    def create_program_with_seats(self):
        currency = Currency.objects.get(code='USD')

        course_run = factories.CourseRunFactory()
        factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
        factories.SeatFactory(type='credit', currency=currency, course_run=course_run, price=600)
        factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=100)

        applicable_seat_types = SeatType.objects.filter(slug__in=['credit', 'verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        return factories.ProgramFactory(type=program_type, courses=[course_run.course])

    def test_str(self):
        """Verify that a program is properly converted to a str."""
        self.assertEqual(str(self.program), self.program.title)

    def test_weeks_to_complete_range(self):
        """ Verify that weeks to complete range works correctly """
        weeks_to_complete_values = [course_run.weeks_to_complete for course_run in self.course_runs]
        expected_min = min(weeks_to_complete_values) if weeks_to_complete_values else None
        expected_max = max(weeks_to_complete_values) if weeks_to_complete_values else None
        self.assertEqual(self.program.weeks_to_complete_min, expected_min)
        self.assertEqual(self.program.weeks_to_complete_max, expected_max)

    def test_marketing_url(self):
        """ Verify the property creates a complete marketing URL. """
        # In test, the factory will likely have the ProgramType's slug and ProgramType's name be the same, we need
        # to verify that the ProgramType's slug is used and not the ProgramType's name; therefore, set the name to
        # something obviously different from the name in order to verify that the correct object is being used.
        self.program.type.slug = '8675309'
        expected = '{root}/{type}/{slug}'.format(root=self.program.partner.marketing_site_url_root.strip('/'),
                                                 type=self.program.type.slug, slug=self.program.marketing_slug)
        self.assertEqual(self.program.marketing_url, expected)

    def test_marketing_url_without_slug(self):
        """ Verify the property returns None if the Program has no marketing_slug set. """
        self.program.marketing_slug = ''
        self.assertIsNone(self.program.marketing_url)

    def test_course_runs(self):
        """
        Verify that we only fetch course runs for the program, and not other course runs for other programs and that the
        property returns the set of associated CourseRuns minus those that are explicitly excluded.
        """
        course_run = factories.CourseRunFactory()
        factories.ProgramFactory(courses=[course_run.course])
        # Verify that course run is not returned in set
        self.assertEqual(set(self.program.course_runs), set(self.course_runs))

    def test_languages(self):
        expected_languages = set([course_run.language for course_run in self.course_runs])
        actual_languages = self.program.languages
        self.assertGreater(len(actual_languages), 0)
        self.assertEqual(actual_languages, expected_languages)

    def test_transcript_languages(self):
        expected_transcript_languages = itertools.chain.from_iterable(
            [list(course_run.transcript_languages.all()) for course_run in self.course_runs])
        expected_transcript_languages = set(expected_transcript_languages)
        actual_transcript_languages = self.program.transcript_languages

        self.assertGreater(len(actual_transcript_languages), 0)
        self.assertEqual(actual_transcript_languages, expected_transcript_languages)

    def test_subjects(self):
        expected_subjects = itertools.chain.from_iterable([list(course.subjects.all()) for course in self.courses])
        expected_subjects = set(expected_subjects)
        actual_subjects = self.program.subjects

        self.assertGreater(len(actual_subjects), 0)
        self.assertEqual(actual_subjects, expected_subjects)

    def test_start(self):
        """ Verify the property returns the minimum start date for the course runs associated with the
        program's courses. """
        expected_start = min([course_run.start for course_run in self.course_runs])
        self.assertEqual(self.program.start, expected_start)

        # Verify start is None for programs with no courses.
        self.program.courses.clear()
        self.assertIsNone(self.program.start)

        # Verify start is None if no course runs have a start date.
        course_run = CourseRunFactory(start=None)
        self.program.courses.add(course_run.course)
        self.assertIsNone(self.program.start)

    def test_price_ranges(self):
        program = self.create_program_with_seats()

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(100), 'max': Decimal(600)}]
        self.assertEqual(program.price_ranges, expected_price_ranges)

    def test_staff(self):
        staff = factories.PersonFactory.create_batch(2)
        self.course_runs[0].staff.add(staff[0])
        self.course_runs[1].staff.add(staff[1])

        self.assertEqual(self.program.staff, set(staff))

    def test_banner_image(self):
        self.program.banner_image = make_image_file('test_banner.jpg')
        self.program.save()
        image_url_prefix = '{}media/programs/banner_images/'.format(settings.MEDIA_URL)
        self.assertIn(image_url_prefix, self.program.banner_image.url)
        for size_key in self.program.banner_image.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(self.program.banner_image, size_key, None)
            self.assertIsNotNone(sized_file)
            self.assertIn(image_url_prefix, sized_file.url)

    def test_seat_types(self):
        program = self.create_program_with_seats()
        self.assertEqual(program.seat_types, set(['credit', 'verified']))

    @ddt.data(ProgramStatus.choices)
    def test_is_active(self, status):
        self.program.status = status
        self.assertEqual(self.program.is_active, status == ProgramStatus.Active)

    @responses.activate
    def test_save_without_publish(self):
        self.program.title = FuzzyText().fuzz()
        self.program.save()
        self.assert_responses_call_count(0)

    @responses.activate
    def test_delete_without_publish(self):
        self.program.delete()
        self.assert_responses_call_count(0)

    @responses.activate
    def test_save_and_publish_success(self):
        self.program.partner.marketing_site_url_root = self.api_root
        self.program.partner.marketing_site_api_username = self.username
        self.program.partner.marketing_site_api_password = self.password
        self.program.type = ProgramType.objects.get(name='MicroMasters')
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_edit(200)
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.title = FuzzyText().fuzz()
        self.mock_add_alias()
        self.mock_delete_alias()
        with mock.patch.object(MarketingSitePublisher, '_get_headers', return_value={}):
            with mock.patch.object(MarketingSitePublisher, '_get_form_build_id_and_form_token', return_value={}):
                with mock.patch.object(MarketingSitePublisher, '_get_delete_alias_url', return_value='/foo'):
                    self.program.save()
                    self.assert_responses_call_count(9)

    @responses.activate
    def test_xseries_program_save(self):
        """
        Make sure if the Program instance is of type XSeries, we do not publish to Marketing Site
        """
        self.program.partner.marketing_site_url_root = self.api_root
        self.program.partner.marketing_site_api_username = self.username
        self.program.partner.marketing_site_api_password = self.password
        self.program.type = ProgramType.objects.get(name='XSeries')
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.title = FuzzyText().fuzz()
        self.program.save()
        self.assert_responses_call_count(0)

    @responses.activate
    def test_save_and_no_marketing_site(self):
        self.program.partner.marketing_site_url_root = None
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.title = FuzzyText().fuzz()
        self.program.save()
        self.assert_responses_call_count(0)

    @responses.activate
    def test_delete_and_publish_success(self):
        self.program.partner.marketing_site_url_root = self.api_root
        self.program.partner.marketing_site_api_username = self.username
        self.program.partner.marketing_site_api_password = self.password
        self.program.type = ProgramType.objects.get(name='MicroMasters')
        self.mock_api_client(200)
        self.mock_node_retrieval(self.program.uuid)
        self.mock_node_delete(204)
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.delete()
        self.assert_responses_call_count(6)

    @responses.activate
    def test_delete_and_no_marketing_site(self):
        self.program.partner.marketing_site_url_root = None
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.delete()
        self.assert_responses_call_count(0)

    def test_course_update_caught_exception(self):
        """ Test that the index update process failing will not cause the program save to error """
        with mock.patch.object(Course, 'reindex_course_runs', side_effect=Exception):
            self.program.save()


class PersonSocialNetworkTests(TestCase):
    """Tests of the PersonSocialNetwork model."""

    def setUp(self):
        super(PersonSocialNetworkTests, self).setUp()
        self.network = factories.PersonSocialNetworkFactory()
        self.person = factories.PersonFactory()

    def test_str(self):
        """Verify that a person-social-network is properly converted to a str."""
        self.assertEqual(
            str(self.network), '{type}: {value}'.format(type=self.network.type, value=self.network.value)
        )

    def test_unique_constraint(self):
        """Verify that a person-social-network does not allow multiple accounts for same
        social network.
        """
        factories.PersonSocialNetworkFactory(person=self.person, type='facebook')
        with self.assertRaises(IntegrityError):
            factories.PersonSocialNetworkFactory(person=self.person, type='facebook')


class CourseSocialNetworkTests(TestCase):
    """Tests of the CourseSocialNetwork model."""

    def setUp(self):
        super(CourseSocialNetworkTests, self).setUp()
        self.network = factories.CourseRunSocialNetworkFactory()
        self.course_run = factories.CourseRunFactory()

    def test_str(self):
        """Verify that a course-social-network is properly converted to a str."""
        self.assertEqual(
            str(self.network), '{type}: {value}'.format(type=self.network.type, value=self.network.value)
        )

    def test_unique_constraint(self):
        """Verify that a course-social-network does not allow multiple accounts for same
        social network.
        """
        factories.CourseRunSocialNetworkFactory(course_run=self.course_run, type='facebook')
        with self.assertRaises(IntegrityError):
            factories.CourseRunSocialNetworkFactory(course_run=self.course_run, type='facebook')


class SeatTypeTests(TestCase):
    """ Tests of the SeatType model. """

    def test_str(self):
        seat_type = factories.SeatTypeFactory()
        self.assertEqual(str(seat_type), seat_type.name)


class ProgramTypeTests(TestCase):
    """ Tests of the ProgramType model. """

    def test_str(self):
        program_type = factories.ProgramTypeFactory()
        self.assertEqual(str(program_type), program_type.name)


class EndorsementTests(TestCase):
    """ Tests of the Endorsement model. """

    def setUp(self):
        super(EndorsementTests, self).setUp()
        self.person = factories.PersonFactory()
        self.endorsement = Endorsement.objects.create(
            endorser=self.person,
            quote='test quote'
        )

    def test_str(self):
        self.assertEqual(str(self.endorsement), self.person.full_name)


class CorporateEndorsementTests(TestCase):
    """ Tests of the CorporateEndorsement model. """

    def setUp(self):
        super(CorporateEndorsementTests, self).setUp()
        self.corporation_name = 'test org'
        self.individual_endorsements = CorporateEndorsement.objects.create(
            corporation_name=self.corporation_name,
            statement='test statement',
            image=ImageFactory()
        )

    def test_str(self):
        self.assertEqual(str(self.individual_endorsements), self.corporation_name)


class FAQTests(TestCase):
    """ Tests of the FAQ model. """

    def test_str(self):
        question = 'test question'
        faq = FAQ.objects.create(question=question, answer='test')
        self.assertEqual(str(faq), question)
