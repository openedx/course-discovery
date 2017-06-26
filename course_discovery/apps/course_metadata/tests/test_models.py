import datetime
import itertools
from decimal import Decimal

import ddt
import mock
from dateutil.parser import parse
from django.conf import settings
from django.db import IntegrityError
from django.db.models.functions import Lower
from django.test import TestCase
from freezegun import freeze_time

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    FAQ, AbstractMediaModel, AbstractNamedModel, AbstractValueModel, CorporateEndorsement, Course, CourseRun,
    Endorsement, Seat, SeatType
)
from course_discovery.apps.course_metadata.publishers import (
    CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.tests import factories, toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ImageFactory
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
        toggle_switch('log_course_search_queries', active=True)
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


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the `CourseRun` model. """

    def setUp(self):
        super(CourseRunTests, self).setUp()
        self.course_run = factories.CourseRunFactory()

    def test_enrollable_seats(self):
        """ Verify the expected seats get returned. """
        course_run = factories.CourseRunFactory(start=None, end=None, enrollment_start=None, enrollment_end=None)
        verified_seat = factories.SeatFactory(course_run=course_run, type=Seat.VERIFIED, upgrade_deadline=None)
        professional_seat = factories.SeatFactory(course_run=course_run, type=Seat.PROFESSIONAL, upgrade_deadline=None)
        factories.SeatFactory(course_run=course_run, type=Seat.HONOR, upgrade_deadline=None)
        self.assertEqual(
            course_run.enrollable_seats([Seat.VERIFIED, Seat.PROFESSIONAL]),
            [verified_seat, professional_seat]
        )

        # The method should not care about the course run's start date.
        course_run.start = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        course_run.save()
        self.assertEqual(
            course_run.enrollable_seats([Seat.VERIFIED, Seat.PROFESSIONAL]),
            [verified_seat, professional_seat]
        )

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
        Verify that paid_seat_enrollment_end returns the latest possible date for which an unenrolled user may
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

    def test_publication_disabled(self):
        """
        Verify that the publisher is not initialized when publication is disabled.
        """
        toggle_switch('publish_course_runs_to_marketing_site', active=False)

        with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
            self.course_run.save()
            self.course_run.delete()

            assert mock_init.call_count == 0

        toggle_switch('publish_course_runs_to_marketing_site')

        with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
            # Make sure if the save comes from refresh_course_metadata, we don't actually publish
            self.course_run.save(suppress_publication=True)
            assert mock_init.call_count == 0

        self.course_run.course.partner.marketing_site_url_root = ''
        self.course_run.course.partner.save()

        with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
            self.course_run.save()
            self.course_run.delete()

            assert mock_init.call_count == 0

    def test_publication_enabled(self):
        """
        Verify that the publisher is called when publication is enabled.
        """
        toggle_switch('publish_course_runs_to_marketing_site')

        with mock.patch.object(CourseRunMarketingSitePublisher, 'publish_obj', return_value=None) as mock_publish_obj:
            self.course_run.save()
            assert mock_publish_obj.called

        with mock.patch.object(CourseRunMarketingSitePublisher, 'delete_obj', return_value=None) as mock_delete_obj:
            self.course_run.delete()
            # We don't want to delete course run nodes when CourseRuns are deleted.
            assert not mock_delete_obj.called


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
class ProgramTests(TestCase):
    """Tests of the Program model."""

    def setUp(self):
        super(ProgramTests, self).setUp()
        transcript_languages = LanguageTag.objects.all()[:2]
        subjects = factories.SubjectFactory.create_batch(2)
        self.course_runs = factories.CourseRunFactory.create_batch(
            3, transcript_languages=transcript_languages, course__subjects=subjects,
            weeks_to_complete=2)
        self.courses = [course_run.course for course_run in self.course_runs]
        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(courses=self.courses, excluded_course_runs=[self.excluded_course_run])

    def create_program_with_seats(self):
        currency = Currency.objects.get(code='USD')

        course_run = factories.CourseRunFactory()
        course_run.course.canonical_course_run = course_run
        course_run.course.save()
        factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
        factories.SeatFactory(type='credit', currency=currency, course_run=course_run, price=600)
        factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=100)

        applicable_seat_types = SeatType.objects.filter(slug__in=['credit', 'verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        return factories.ProgramFactory(type=program_type, courses=[course_run.course])

    def assert_one_click_purchase_ineligible_program(
        self, end=None, enrollment_start=None, enrollment_end=None, seat_type=Seat.VERIFIED,
        upgrade_deadline=None, one_click_purchase_enabled=True, excluded_course_runs=None, program_type=None
    ):
        course_run = factories.CourseRunFactory(
            end=end, enrollment_start=enrollment_start, enrollment_end=enrollment_end
        )
        factories.SeatFactory(course_run=course_run, type=seat_type, upgrade_deadline=upgrade_deadline)
        program = factories.ProgramFactory(
            courses=[course_run.course],
            excluded_course_runs=excluded_course_runs,
            one_click_purchase_enabled=one_click_purchase_enabled,
            type=program_type,
        )
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_eligible(self):
        """ Verify that program is one click purchase eligible. """
        verified_seat_type, __ = SeatType.objects.get_or_create(name=Seat.VERIFIED)
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])

        # Program has one_click_purchase_enabled set to True,
        # all courses have one course run, all course runs have
        # verified seat types
        courses = []
        for __ in range(3):
            course_run = factories.CourseRunFactory(
                end=None,
                enrollment_end=None
            )
            factories.SeatFactory(course_run=course_run, type=Seat.VERIFIED, upgrade_deadline=None)
            courses.append(course_run.course)
        program = factories.ProgramFactory(
            courses=courses,
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

        # Program has one_click_purchase_enabled set to True,
        # course has all course runs excluded except one which
        # has verified seat type
        course_run = factories.CourseRunFactory(
            end=None,
            enrollment_end=None
        )
        factories.SeatFactory(course_run=course_run, type=Seat.VERIFIED, upgrade_deadline=None)
        course = course_run.course
        excluded_course_runs = [
            factories.CourseRunFactory(course=course),
            factories.CourseRunFactory(course=course)
        ]
        program = factories.ProgramFactory(
            courses=[course],
            excluded_course_runs=excluded_course_runs,
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_eligible_with_unpublished_runs(self):
        """ Verify that program with unpublished course runs is one click purchase eligible. """

        verified_seat_type, __ = SeatType.objects.get_or_create(name=Seat.VERIFIED)
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])
        published_course_run = factories.CourseRunFactory(
            end=None,
            enrollment_end=None,
            status=CourseRunStatus.Published
        )
        unpublished_course_run = factories.CourseRunFactory(
            end=None,
            enrollment_end=None,
            status=CourseRunStatus.Unpublished,
            course=published_course_run.course
        )
        factories.SeatFactory(course_run=published_course_run, type=Seat.VERIFIED, upgrade_deadline=None)
        factories.SeatFactory(course_run=unpublished_course_run, type=Seat.VERIFIED, upgrade_deadline=None)
        program = factories.ProgramFactory(
            courses=[published_course_run.course],
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_ineligible(self):
        """ Verify that program is one click purchase ineligible. """
        yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        verified_seat_type, __ = SeatType.objects.get_or_create(name=Seat.VERIFIED)
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])

        # Program has one_click_purchase_enabled set to False and
        # every course has one course run
        self.assert_one_click_purchase_ineligible_program(
            one_click_purchase_enabled=False,
            program_type=program_type,
        )

        # Program has one_click_purchase_enabled set to True and
        # one course has two course runs
        course_run = factories.CourseRunFactory(end=None, enrollment_end=None)
        factories.CourseRunFactory(end=None, enrollment_end=None, course=course_run.course)
        factories.SeatFactory(course_run=course_run, type='verified', upgrade_deadline=None)
        program = factories.ProgramFactory(
            courses=[course_run.course],
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

        # Program has one_click_purchase_enabled set to True and
        # one course with one course run excluded from the program
        course_run = factories.CourseRunFactory(end=None, enrollment_end=None)
        factories.SeatFactory(course_run=course_run, type='verified', upgrade_deadline=None)
        program = factories.ProgramFactory(
            courses=[course_run.course],
            one_click_purchase_enabled=True,
            excluded_course_runs=[course_run],
            type=program_type,
        )
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

        # Program has one_click_purchase_enabled set to True, one course
        # with one course run, course run end date passed
        self.assert_one_click_purchase_ineligible_program(
            end=yesterday,
            program_type=program_type,
        )

        # Program has one_click_purchase_enabled set to True, one course
        # with one course run, course run enrollment start date not passed
        self.assert_one_click_purchase_ineligible_program(
            enrollment_start=tomorrow,
            program_type=program_type,
        )

        # Program has one_click_purchase_enabled set to True, one course
        # with one course run, course run enrollment end date passed
        self.assert_one_click_purchase_ineligible_program(
            enrollment_end=yesterday,
            program_type=program_type,
        )

        # Program has one_click_purchase_enabled set to True, one course
        # with one course run, seat upgrade deadline passed
        self.assert_one_click_purchase_ineligible_program(
            upgrade_deadline=yesterday,
            program_type=program_type,
        )

        # Program has one_click_purchase_enabled set to True, one course
        # with one course run, seat type is not purchasable
        self.assert_one_click_purchase_ineligible_program(
            seat_type='incorrect',
            program_type=program_type,
        )

    def test_str(self):
        """Verify that a program is properly converted to a str."""
        self.assertEqual(str(self.program), self.program.title)

    def test_weeks_to_complete_range(self):
        """ Verify that weeks to complete range works correctly """
        weeks_to_complete_values = [course_run.weeks_to_complete for course_run in self.course_runs]
        for course_run in self.course_runs:
            course = course_run.course
            course.canonical_course_run = course_run
            course.save()

        expected_min = min(weeks_to_complete_values) if weeks_to_complete_values else None
        expected_max = max(weeks_to_complete_values) if weeks_to_complete_values else None
        # property does not have the right values while being indexed
        del self.program._course_run_weeks_to_complete
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

    def test_canonical_course_runs(self):
        course = self.course_runs[0].course
        course.canonical_course_run = self.course_runs[0]
        course.save()

        course = self.course_runs[1].course
        course.canonical_course_run = self.course_runs[1]
        course.save()

        expected_canonical_runs = [self.course_runs[0], self.course_runs[1]]
        # Verify only canonical course runs are returned in set
        self.assertEqual(set(self.program.canonical_course_runs), set(expected_canonical_runs))

    def test_canonical_course_seats(self):
        """ Test canonical course seats returns only canonical course run's applicable seats """
        currency = Currency.objects.get(code='USD')

        course = factories.CourseFactory()
        course_runs_same_course = factories.CourseRunFactory.create_batch(3, course=course)
        for course_run in course_runs_same_course:
            factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=100)
        course.canonical_course_run = course_runs_same_course[0]
        course.save()

        applicable_seat_types = SeatType.objects.filter(slug__in=['verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        program = factories.ProgramFactory(type=program_type, courses=[course])

        self.assertEqual(set(course.canonical_course_run.seats.all()), set(program.canonical_seats))

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
        """ Verify the price_ranges property of the program is returning expected price values """
        program = self.create_program_with_seats()

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(100), 'max': Decimal(600), 'total': Decimal(600)}]
        self.assertEqual(program.price_ranges, expected_price_ranges)

    def test_price_ranges_multiple_course(self):
        """ Verifies the price_range property of a program with multiple courses """
        currency = Currency.objects.get(code='USD')
        test_price = 100
        for course_run in self.course_runs:
            factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=test_price)
            test_price += 100
            course_run.course.canonical_course_run = course_run
            course_run.course.save()

        applicable_seat_types = SeatType.objects.filter(slug__in=['verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        self.program.type = program_type

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(100), 'max': Decimal(300), 'total': Decimal(600)}]
        self.assertEqual(self.program.price_ranges, expected_price_ranges)

    def create_program_with_multiple_course_runs(self, set_all_dates=True):
        currency = Currency.objects.get(code='USD')
        single_course_course_runs = factories.CourseRunFactory.create_batch(3)
        course = factories.CourseFactory()
        course_runs_same_course = factories.CourseRunFactory.create_batch(3, course=course)
        for course_run in single_course_course_runs:
            factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=10)
            course_run.course.canonical_course_run = course_run
            course_run.course.save()

        day_separation = 1
        now = datetime.datetime.utcnow()

        for course_run in course_runs_same_course:
            if set_all_dates or day_separation < 2:
                date_delta = datetime.timedelta(days=day_separation)
                course_run.enrollment_start = now - date_delta
                course_run.end = now + datetime.timedelta(weeks=day_separation)
            else:
                course_run.enrollment_start = None
                course_run.end = None
            course_run.save()
            factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(
                type='verified',
                currency=currency,
                course_run=course_run,
                price=(day_separation * 100))
            day_separation += 1
        course.canonical_course_run = course_runs_same_course[2]
        course.save()
        applicable_seat_types = SeatType.objects.filter(slug__in=['verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        program_courses = [course_run.course for course_run in single_course_course_runs]
        program_courses.append(course)

        return factories.ProgramFactory(type=program_type, courses=program_courses)

    def test_price_ranges_with_multiple_course_runs(self):
        """
        Verifies the price_range property of a program with multiple courses,
        and a course with multiple runs
        """
        program = self.create_program_with_multiple_course_runs()

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(10), 'max': Decimal(300), 'total': Decimal(330)}]
        self.assertEqual(program.price_ranges, expected_price_ranges)

    def test_price_ranges_with_multiple_course_runs_and_none_dates(self):
        """
        Verifies the price_range property of a program with multiple courses,
        and a course with multiple runs, and some of the dates in the course runs are None
        """

        program = self.create_program_with_multiple_course_runs(set_all_dates=False)

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(10), 'max': Decimal(300), 'total': Decimal(330)}]
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

    def test_publication_disabled(self):
        """
        Verify that the publisher is not initialized when publication is disabled.
        """
        toggle_switch('publish_program_to_marketing_site', active=False)

        with mock.patch.object(ProgramMarketingSitePublisher, '__init__') as mock_init:
            self.program.save()
            self.program.delete()

            assert mock_init.call_count == 0

        toggle_switch('publish_program_to_marketing_site')
        self.program.partner.marketing_site_url_root = ''
        self.program.partner.save()

        with mock.patch.object(ProgramMarketingSitePublisher, '__init__') as mock_init:
            self.program.save()
            self.program.delete()

            assert mock_init.call_count == 0

    def test_publication_enabled(self):
        """
        Verify that the publisher is called when publication is enabled.
        """
        toggle_switch('publish_program_to_marketing_site')

        with mock.patch.object(ProgramMarketingSitePublisher, 'publish_obj', return_value=None) as mock_publish_obj:
            self.program.save()
            assert mock_publish_obj.called

        with mock.patch.object(ProgramMarketingSitePublisher, 'delete_obj', return_value=None) as mock_delete_obj:
            self.program.delete()
            assert mock_delete_obj.called


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
