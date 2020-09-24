# -*- coding: utf-8 -*-

import datetime
import itertools
import uuid
from decimal import Decimal
from functools import partial

import ddt
import mock
import pytest
import pytz
import responses
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from freezegun import freeze_time
from taggit.models import Tag
from testfixtures import LogCapture
from waffle.testutils import override_switch

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    FAQ, AbstractMediaModel, AbstractNamedModel, AbstractTitleDescriptionModel, AbstractValueModel,
    CorporateEndorsement, Course, CourseEditor, CourseRun, Curriculum, CurriculumCourseMembership,
    CurriculumCourseRunExclusion, CurriculumProgramMembership, DegreeCost, DegreeDeadline, Endorsement, Organization,
    Program, Ranking, Seat, SeatType, Subject, Topic
)
from course_discovery.apps.course_metadata.publishers import (
    CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.course_metadata.tests.factories import (
    CourseRunFactory, ImageFactory, SeatFactory, SeatTypeFactory
)
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.course_metadata.utils import ensure_draft_world
from course_discovery.apps.course_metadata.utils import logger as utils_logger
from course_discovery.apps.course_metadata.utils import uslugify
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
@ddt.ddt
class TestCourse(TestCase):
    def test_str(self):
        course = factories.CourseFactory()
        assert str(course), '{key}: {title}'.format(key=course.key, title=course.title)

    def test_search(self):
        title = 'Some random title'
        expected = set(factories.CourseFactory.create_batch(3, title=title))
        query = 'title:' + title
        assert set(Course.search(query)) == expected

    def test_wildcard_search(self):
        expected = set(factories.CourseFactory.create_batch(3))
        assert set(Course.search('*')) == expected

    def test_image_url(self):
        course = factories.CourseFactory()
        assert course.image_url == course.image.small.url

        course.image = None
        assert course.image_url == course.card_image_url

    def test_original_image_url(self):
        course = factories.CourseFactory()
        assert course.original_image_url == course.image.url

        course.image = None
        assert course.original_image_url is None

    @ddt.data('faq', 'full_description', 'learner_testimonials', 'outcome', 'prerequisites_raw', 'short_description',
              'syllabus_raw')
    def test_html_fields_are_validated(self, field_name):
        course = factories.CourseFactory()

        # Happy path
        setattr(course, field_name, '<p>')
        course.clean_fields()

        # Bad HTML
        setattr(course, field_name, '<?proc>')
        with self.assertRaises(ValidationError) as cm:
            course.clean_fields()
        self.assertEqual(cm.exception.message_dict[field_name], ['Invalid HTML received'])

    def test_first_enrollable_paid_seat_price(self):
        """
        Verify that `first_enrollable_paid_seat_price` property for a course
        returns price of first paid seat of first active course run.
        """
        now = datetime.datetime.now(pytz.UTC)
        active_course_end = now + datetime.timedelta(days=60)
        open_enrollment_end = now + datetime.timedelta(days=30)

        course = factories.CourseFactory()
        # Create and active course run with end date in future and enrollment_end in future.
        course_run = CourseRunFactory(
            course=course,
            end=active_course_end,
            enrollment_end=open_enrollment_end
        )
        verified_type = factories.SeatTypeFactory.verified()
        # Create a seat with 0 price and verify that the course field
        # `first_enrollable_paid_seat_price` returns None
        factories.SeatFactory.create(course_run=course_run, type=verified_type, price=0, sku='ABCDEF')
        assert course_run.first_enrollable_paid_seat_price is None
        assert course.first_enrollable_paid_seat_price is None

        # Now create a seat with some price and verify that the course field
        # `first_enrollable_paid_seat_price` now returns the price of that
        # payable seat
        factories.SeatFactory.create(course_run=course_run, type=verified_type, price=100, sku='ABCDEF')
        assert course_run.first_enrollable_paid_seat_price == 100
        assert course.first_enrollable_paid_seat_price == 100

    def test_course_run_sort(self):
        course = factories.CourseFactory.create()
        now = datetime.datetime.now(pytz.UTC)
        first_course_run = factories.CourseRunFactory.create(
            enrollment_start=now - datetime.timedelta(days=100),
            start=now + datetime.timedelta(days=100),
        )
        second_course_run = factories.CourseRunFactory.create(
            enrollment_start=now - datetime.timedelta(days=50),
            start=None,
        )
        third_course_run = factories.CourseRunFactory.create(
            enrollment_start=None,
            start=now + datetime.timedelta(days=50),
        )
        fourth_course_run = factories.CourseRunFactory.create(
            enrollment_start=None,
            start=None,
        )

        out_of_order_runs = [
            third_course_run,
            second_course_run,
            first_course_run,
            fourth_course_run,
        ]
        expected_order = [
            first_course_run,
            second_course_run,
            third_course_run,
            fourth_course_run,
        ]
        self.assertEqual(sorted(out_of_order_runs, key=course.course_run_sort), expected_order)


class TestCourseUpdateMarketingUnpublish(MarketingSitePublisherTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = factories.CourseFactory()
        cls.partner = cls.course.partner
        cls.past = datetime.datetime(2010, 1, 1, tzinfo=pytz.UTC)
        cls.future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        cls.base_args = {'course': cls.course, 'status': CourseRunStatus.Published}
        cls.active = factories.CourseRunFactory(end=cls.future, enrollment_end=cls.future, **cls.base_args)
        cls.inactive = factories.CourseRunFactory(end=cls.past, **cls.base_args)
        ensure_draft_world(Course.objects.get(pk=cls.course.pk))
        cls.api_root = cls.partner.marketing_site_url_root.rstrip('/')  # overwrite the mixin's version

    def assertUnpublish(self, published_runs=None, succeed=True):
        """
        Args:
            published_runs: Runs to pass to the unpublish call
            succeed: Whether the unpublish should return True or False
        """

        self.assertEqual(self.course.unpublish_inactive_runs(published_runs=published_runs), succeed)

        if succeed:
            self.active.refresh_from_db()
            self.assertEqual(self.active.status, CourseRunStatus.Published)  # should have stayed the same

            self.inactive.refresh_from_db()
            self.assertEqual(self.inactive.status, CourseRunStatus.Unpublished)
            if self.inactive.draft_version:
                self.assertEqual(self.inactive.draft_version.status, CourseRunStatus.Unpublished)

    def test_simple_happy_path(self):
        self.assertUnpublish()

    def test_no_marketing_site(self):
        # Without
        self.partner.marketing_site_url_root = None
        self.partner.save()
        self.assertUnpublish(succeed=False)

        # Confirm that with will work
        self.partner.marketing_site_url_root = self.api_root
        self.partner.save()
        self.assertUnpublish()

    def test_ignores_unpublished(self):
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.Unpublished, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.Reviewed, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.InternalReview, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.LegalReview, end=self.past)
        self.assertUnpublish()

    def test_accepts_run_list(self):
        self.assertUnpublish(published_runs={self.active, self.inactive})

    def test_uses_earliest_of_end_or_enrollment_end(self):
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        _no_end = factories.CourseRunFactory(**self.base_args, end=None, enrollment_end=self.past)
        _no_enrollment_end = factories.CourseRunFactory(**self.base_args, end=self.past, enrollment_end=None)
        _earlier_end = factories.CourseRunFactory(**self.base_args, end=self.past, enrollment_end=future)
        _earlier_enrollment_end = factories.CourseRunFactory(**self.base_args, end=future, enrollment_end=self.past)
        _in_future = factories.CourseRunFactory(**self.base_args, end=future, enrollment_end=future, start=future)
        self.assertUnpublish()

    def test_leaves_at_least_one_run_published(self):
        """ Verifies that we refuse to unpublish all runs in a course if there are no marketable runs. """
        self.active.end = self.past
        self.active.enrollment_end = self.past
        self.active.save()
        self.assertUnpublish(succeed=False)  # fails if no marketable runs at all


class TestCourseEditor(TestCase):
    """ Tests for the CourseEditor module. """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = factories.UserFactory()
        cls.courses_qs = Course.objects.all()
        cls.runs_qs = CourseRun.objects.all()

        cls.org_ext = OrganizationExtensionFactory()

        # *** Add a bunch of courses ***

        # Course with no editors
        cls.course_no_editors = factories.CourseFactory(title="no editors")
        cls.run_no_editors = factories.CourseRunFactory(course=cls.course_no_editors)

        # Course with an invalid editor (no group membership)
        bad_editor = factories.UserFactory()
        cls.course_bad_editor = factories.CourseFactory(title="bad editor")
        cls.run_bad_editor = factories.CourseRunFactory(course=cls.course_bad_editor)
        factories.CourseEditorFactory(user=bad_editor, course=cls.course_bad_editor)

        # Course with an invalid editor (but course is in our group)
        cls.course_bad_editor_in_group = factories.CourseFactory(title="bad editor in group")
        cls.course_bad_editor_in_group.authoring_organizations.add(cls.org_ext.organization)
        cls.run_bad_editor_in_group = factories.CourseRunFactory(course=cls.course_bad_editor_in_group)
        factories.CourseEditorFactory(user=bad_editor, course=cls.course_bad_editor_in_group)

        # Course with a valid other editor
        cls.good_editor = factories.UserFactory()
        cls.good_editor.groups.add(cls.org_ext.group)
        cls.course_good_editor = factories.CourseFactory(title="good editor")
        cls.course_good_editor.authoring_organizations.add(cls.org_ext.organization)
        cls.run_good_editor = factories.CourseRunFactory(course=cls.course_good_editor)
        factories.CourseEditorFactory(user=cls.good_editor, course=cls.course_good_editor)

        # Course with user as an invalid editor (no group membership)
        cls.course_no_group = factories.CourseFactory(title="no group")
        cls.run_no_group = factories.CourseRunFactory(course=cls.course_no_group)
        factories.CourseEditorFactory(user=cls.user, course=cls.course_no_group)

        # Course with user as an valid editor
        cls.course_editor = factories.CourseFactory(title="editor")
        cls.course_editor.authoring_organizations.add(cls.org_ext.organization)
        cls.run_editor = factories.CourseRunFactory(course=cls.course_editor)
        factories.CourseEditorFactory(user=cls.user, course=cls.course_editor)

        # Add another authoring_org, which will cause django to return duplicates, if we don't filter them out
        org_ext2 = OrganizationExtensionFactory()
        cls.user.groups.add(org_ext2.group)
        cls.course_editor.authoring_organizations.add(org_ext2.organization)
        cls.course_bad_editor_in_group.authoring_organizations.add(org_ext2.organization)

    def setUp(self):
        """ Resets self.user to not be staff and to belong to the self.org_ext group. """
        super().setUp()
        self.user.groups.add(self.org_ext.group)
        self.user.is_staff = False
        self.user.save()

    def filter_editable_courses(self):
        return CourseEditor.editable_courses(self.user, self.courses_qs)

    def filter_editable_course_runs(self):
        return CourseEditor.editable_course_runs(self.user, self.runs_qs)

    def assertResultsEqual(self, method, expected_result, queries=None):
        if queries is None:
            result = list(method())
        else:
            with self.assertNumQueries(queries):
                result = list(method())

        self.assertEqual(len(result), len(expected_result))
        self.assertEqual(set(result), set(expected_result))

    def test_editable_is_staff(self):
        """ Verify staff users can see everything. """
        self.user.is_staff = True
        self.user.save()
        self.assertResultsEqual(self.filter_editable_courses, self.courses_qs)
        self.assertResultsEqual(self.filter_editable_course_runs, self.runs_qs)

    def test_editable_no_access(self):
        """ Verify users without any editor status see nothing. """
        self.user.groups.clear()
        self.assertResultsEqual(self.filter_editable_courses, [], queries=1)
        self.assertResultsEqual(self.filter_editable_course_runs, [], queries=1)

    def test_editable_filter(self):
        """ Verify users can see courses they can edit. """
        self.assertResultsEqual(self.filter_editable_courses, {self.course_bad_editor_in_group, self.course_editor},
                                queries=1)
        self.assertResultsEqual(self.filter_editable_course_runs, {self.run_bad_editor_in_group, self.run_editor},
                                queries=1)

    def test_editable_without_checking_editors(self):
        """ Verify the that we can get a list of *potentially editable* courses (courses in org). """
        self.assertResultsEqual(
            partial(CourseEditor.editable_courses, self.user, self.courses_qs, check_editors=False),
            {self.course_bad_editor_in_group, self.course_good_editor, self.course_editor},
            queries=1,
        )

    def test_course_editors_when_valid_editors(self):
        self.assertResultsEqual(partial(CourseEditor.course_editors, self.course_editor), {self.user}, queries=1)

    def test_course_editors_when_no_editors(self):
        # two queries: one to check for valid editors, one for everybody in group
        self.assertResultsEqual(
            partial(CourseEditor.course_editors, self.course_bad_editor_in_group),
            {self.user, self.good_editor},
            queries=2,
        )

    def test_editors_for_user(self):
        """Verify that the editors_for_user method returns editors for a give user"""
        # tests number of editors against the editors established in the setUp method above
        editors = CourseEditor.editors_for_user(self.user)
        assert len(editors) == 5


@ddt.ddt
class CourseRunTests(OAuth2Mixin, TestCase):
    """ Tests for the `CourseRun` model. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course_run = factories.CourseRunFactory()
        cls.partner = cls.course_run.course.partner

    def setUp(self):
        """ Reset self.course_run and self.partner to whatever the DB says. """
        super().setUp()
        self.course_run.refresh_from_db()
        self.course_run.course.refresh_from_db()
        self.partner.refresh_from_db()

    def test_enrollable_seats(self):
        """ Verify the expected seats get returned. """
        course_run = factories.CourseRunFactory(start=None, end=None, enrollment_start=None, enrollment_end=None)
        verified_seat_type = factories.SeatTypeFactory.verified()
        professional_seat_type = factories.SeatTypeFactory.professional()
        honor_seat_type = factories.SeatTypeFactory.honor()
        verified_seat = factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
        professional_seat = factories.SeatFactory(course_run=course_run, type=professional_seat_type,
                                                  upgrade_deadline=None)
        honor_seat = factories.SeatFactory(course_run=course_run, type=honor_seat_type, upgrade_deadline=None)
        self.assertEqual(course_run.enrollable_seats([verified_seat_type, professional_seat_type]),
                         [verified_seat, professional_seat])

        # The method should not care about the course run's start date.
        course_run.start = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        course_run.save()
        self.assertEqual(course_run.enrollable_seats([verified_seat_type, professional_seat_type]),
                         [verified_seat, professional_seat])

        # Enrollable seats of any type should be returned when no type parameter is specified.
        self.assertEqual(course_run.enrollable_seats(), [verified_seat, professional_seat, honor_seat])

    def test_has_enrollable_seats(self):
        """ Verify the expected value of has_enrollable_seats is returned. """
        course_run = factories.CourseRunFactory(start=None, end=None, enrollment_start=None, enrollment_end=None)
        factories.SeatFactory(course_run=course_run, type=factories.SeatTypeFactory.verified(), upgrade_deadline=None)
        assert course_run.has_enrollable_seats is True

        course_run.end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        course_run.save()
        assert course_run.has_enrollable_seats is False

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        course_run = self.course_run
        self.assertEqual(str(course_run), '{key}: {title}'.format(key=course_run.key, title=course_run.title))

    @ddt.data('full_description_override', 'outcome_override', 'short_description_override')
    def test_html_fields_are_validated(self, field_name):
        # Happy path
        setattr(self.course_run, field_name, '<p>')
        self.course_run.clean_fields()

        # Bad HTML
        setattr(self.course_run, field_name, '<?proc>')
        with self.assertRaises(ValidationError) as cm:
            self.course_run.clean_fields()
        self.assertEqual(cm.exception.message_dict[field_name], ['Invalid HTML received'])

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

    def test_wildcard_search(self):
        """ Verify the method returns an unfiltered queryset of course runs. """
        course_runs = factories.CourseRunFactory.create_batch(3)
        actual_sorted = sorted(SearchQuerySetWrapper(CourseRun.search('*')), key=lambda course_run: course_run.key)
        expected_sorted = sorted(course_runs + [self.course_run], key=lambda course_run: course_run.key)
        self.assertEqual(actual_sorted, expected_sorted)

    def test_seat_types(self):
        """ Verify the property returns a list of all seat types associated with the course run. """
        self.assertEqual(self.course_run.seat_types, [])

        seats = factories.SeatFactory.create_batch(3, course_run=self.course_run)
        expected = sorted(seat.type.slug for seat in seats)
        self.assertEqual(sorted(seat_type.slug for seat_type in self.course_run.seat_types), expected)

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
    def test_type_legacy(self, seat_types, expected_course_run_type):
        """ Verify the property returns the appropriate type string for the CourseRun. """
        for seat_type in seat_types:
            type_obj = SeatType.objects.update_or_create(slug=seat_type, defaults={'name': seat_type})[0]
            factories.SeatFactory(course_run=self.course_run, type=type_obj)
        self.assertEqual(self.course_run.type_legacy, expected_course_run_type)

    def test_level_type(self):
        """ Verify the property returns the associated Course's level type. """
        self.assertEqual(self.course_run.level_type, self.course_run.course.level_type)

    @freeze_time('2016-06-21 00:00:00Z')
    @ddt.data(
        (None, None, 'Upcoming'),
        ('2030-01-01 00:00:00Z', None, 'Upcoming'),
        (None, '2016-01-01 00:00:00Z', 'Archived'),
        ('2015-01-01 00:00:00Z', '2016-01-01 00:00:00Z', 'Archived'),
        ('2015-10-24 00:00:00Z', None, 'Current'),
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
        expected = '{root}/course/{slug}'.format(root=self.partner.marketing_site_url_root.strip('/'),
                                                 slug=self.course_run.slug)
        self.assertEqual(self.course_run.marketing_url, expected)

    def test_marketing_url_with_empty_marketing_slug(self):
        """ Verify the property returns None if the CourseRun has no marketing_slug value. """
        self.course_run.slug = ''
        self.assertIsNone(self.course_run.marketing_url)

    def test_slug_defined_on_create(self):
        """ Verify the slug is created on first save from the title and key. """
        course_run = CourseRunFactory(title='Test Title')
        slug_key = uslugify(course_run.key)
        self.assertEqual(course_run.slug, 'test-title-{slug_key}'.format(slug_key=slug_key))

    def test_empty_slug_defined_on_save(self):
        """ Verify the slug is defined on save if it wasn't set already. """
        self.course_run.slug = ''
        self.course_run.title = 'Test Title'
        self.course_run.save()
        slug_key = uslugify(self.course_run.key)
        self.assertEqual(self.course_run.slug, 'test-title-{slug_key}'.format(slug_key=slug_key))

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

    def test_new_course_run_excluded_in_retired_programs(self):
        """ Verify the newly created course run must be excluded in associated retired programs"""
        course = factories.CourseFactory()
        course_run = factories.CourseRunFactory(course=course)
        program = factories.ProgramFactory(
            courses=[course], status=ProgramStatus.Retired,
        )
        course_run.weeks_to_complete = 2
        course_run.save()
        new_course_run = factories.CourseRunFactory(course=course)
        new_course_run.save()
        self.assertEqual(program.excluded_course_runs.count(), 1)
        self.assertEqual(len(list(program.course_runs)), 1)

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
            factories.SeatFactory.create(course_run=course_run, type=SeatType.objects.get(slug=seat_type), price=price)
        self.assertEqual(course_run.has_enrollable_paid_seats(), expected_result)

    def test_first_enrollable_paid_seat_sku(self):
        """
        Verify that first_enrollable_paid_seat_sku returns sku of first paid seat.
        """
        course_run = factories.CourseRunFactory.create()
        factories.SeatFactory.create(course_run=course_run, type=factories.SeatTypeFactory.verified(), price=10,
                                     sku='ABCDEF')
        self.assertEqual(course_run.first_enrollable_paid_seat_sku(), 'ABCDEF')

    def test_first_enrollable_paid_seat_price(self):
        """
        Verify that first_enrollable_paid_seat_price returns price of first paid seat.
        """
        course_run = factories.CourseRunFactory.create()
        factories.SeatFactory.create(course_run=course_run, type=factories.SeatTypeFactory.verified(), price=10,
                                     sku='ABCDEF')
        self.assertEqual(course_run.first_enrollable_paid_seat_price, 10)

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
            factories.SeatFactory.create(course_run=course_run, type=SeatType.objects.get(slug=seat_type), price=price,
                                         upgrade_deadline=deadline)

        expected_result = parse(expected_result) if expected_result else None
        self.assertEqual(course_run.get_paid_seat_enrollment_end(), expected_result)

    now = datetime.datetime.now(pytz.timezone('utc'))
    one_month = relativedelta(months=1)
    two_weeks = relativedelta(days=14)

    @ddt.data(
        (None, None, None, False),
        (now - one_month, None, None, False),
        (now - one_month, now + one_month, None, True),
        (now - one_month, now - one_month, now - two_weeks, False),
        (now - one_month, now + one_month, now - two_weeks, False),
        (now - one_month, now + one_month, now + two_weeks, True),
        (now + one_month, now + one_month, now + two_weeks, False),
    )
    @ddt.unpack
    def test_is_current_and_still_upgradeable(self, start, end, deadline, is_current):
        """
        Verify that is_current_and_still_upgradeable returns true if
        1. Today is after the run start (or start is none) and two weeks from the run end (or end is none)
        2. The run has a seat that is still enrollable and upgradeable
        and false otherwise
        """
        course_run = factories.CourseRunFactory.create(start=start, end=end, enrollment_end=end)
        factories.SeatFactory.create(course_run=course_run, upgrade_deadline=deadline,
                                     type=factories.SeatTypeFactory.verified(), price=1)
        assert course_run.is_current_and_still_upgradeable() == is_current

    def test_image_url(self):
        assert self.course_run.image_url == self.course_run.course.image_url

    def test_get_video(self):
        assert self.course_run.get_video == self.course_run.video
        self.course_run.video = None
        self.course_run.save()
        assert self.course_run.get_video == self.course_run.course.video

    @ddt.data(
        (None, False),
        (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10), False),
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10), True),
    )
    @ddt.unpack
    @mock.patch('course_discovery.apps.course_metadata.emails.send_email_for_reviewed')
    def test_reviewed_with_go_live_date(self, when, published, mock_email):
        draft = factories.CourseRunFactory(
            draft=True,
            go_live_date=when,
            announcement=None,
        )
        end = when + datetime.timedelta(days=50) if when else None
        if end:  # Both end and enrollment_end need to be in the future or else runs will be set to unpublished
            draft.end = end
            draft.enrollment_end = end
        draft.course.draft = True
        draft.course.save()

        # force this prop to be cached, to catch any errors if we assume .official_version is valid after creation
        self.assertIsNone(draft.official_version)

        draft.status = CourseRunStatus.Reviewed
        draft.save()
        draft.refresh_from_db()
        official_version = CourseRun.objects.get(key=draft.key)

        for run in [draft, official_version]:
            if published:
                self.assertEqual(run.status, CourseRunStatus.Published)
                self.assertIsNotNone(run.announcement)
                self.assertEqual(mock_email.call_count, 0)
            else:
                self.assertEqual(run.status, CourseRunStatus.Reviewed)
                self.assertIsNone(run.announcement)
                self.assertEqual(mock_email.call_count, 1)

    def test_publish_ignores_draft_input(self):
        draft = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, draft=True)
        self.assertFalse(draft.publish())
        self.assertEqual(draft.status, CourseRunStatus.Unpublished)

    def test_publish_affects_draft_version_too(self):
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        draft = factories.CourseRunFactory(
            status=CourseRunStatus.Unpublished, announcement=None,
            draft=True, end=end, enrollment_end=end,
        )
        official = factories.CourseRunFactory(
            status=CourseRunStatus.Unpublished, announcement=None, draft=False,
            course=draft.course, draft_version=draft, end=end, enrollment_end=end,
        )

        self.assertTrue(official.publish())
        draft.refresh_from_db()

        self.assertEqual(draft.status, CourseRunStatus.Published)
        self.assertIsNotNone(draft.announcement)
        self.assertEqual(official.status, CourseRunStatus.Published)
        self.assertIsNotNone(official.announcement)

    def test_publish_adds_slug_to_course(self):
        to_publish = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, draft=False)
        current_active_course_slug = to_publish.course.active_url_slug
        to_publish.publish()
        all_slugs_as_list = [slug_obj.url_slug for slug_obj in to_publish.course.url_slug_history.all()]
        self.assertIn(to_publish.slug, all_slugs_as_list)
        self.assertEqual(to_publish.course.active_url_slug, current_active_course_slug)

    def test_publish_does_not_add_duplicate_slugs(self):
        course = factories.CourseFactory(draft=False)
        to_publish = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, draft=False, course=course)
        course.set_active_url_slug(to_publish.slug)
        to_publish.publish()
        self.assertEqual(course.active_url_slug, to_publish.slug)
        self.assertEqual(course.url_slug_history.count(), 2)

    def test_publish_errors_if_slug_exists_on_other_course(self):
        course1 = factories.CourseFactory(draft=False)
        course2 = factories.CourseFactory(draft=False, partner=course1.partner)
        to_publish = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, draft=False, course=course1)
        course2.set_active_url_slug(to_publish.slug)
        with self.assertRaises(IntegrityError):
            to_publish.publish()

    @ddt.data(
        (None, None, True),  # No enrollment start or end
        (
            datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10),
            None,
            True,
        ),  # Enroll start in past, no enroll end
        (
            datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            None,
            False,
        ),  # Enroll start in future, no enroll end
        (
            None,
            datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10),
            False,
        ),  # No enroll start, enroll end in past
        (
            None,
            datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            True,
        ),  # No enroll start, enroll end in future
        (
            datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10),
            datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
            True,
        ),  # Enroll start in past, enroll end in future
    )
    @ddt.unpack
    def test_is_enrollable(self, enrollment_start, enrollment_end, expected):
        course_run = factories.CourseRunFactory.create(
            end=None, enrollment_start=enrollment_start, enrollment_end=enrollment_end,
        )
        self.assertEqual(course_run.is_enrollable, expected)

    @ddt.data(
        (CourseRunStatus.Unpublished, False, False, False),  # Not published, no seats, no marketing url
        (CourseRunStatus.Unpublished, False, True, False),  # Not published, no seats, marketing url
        (CourseRunStatus.Unpublished, True, False, False),  # Not published, seats, no marketing url
        (CourseRunStatus.Unpublished, True, False, False),  # Not published, seats, marketing url
        (CourseRunStatus.Published, False, False, False),  # Published, no seats, no marketing url
        (CourseRunStatus.Published, True, False, False),  # Published, seats, no marketing url
        (CourseRunStatus.Published, False, True, False),  # Published, no seats, marketing url
        (CourseRunStatus.Published, True, True, True),  # Published, seats, marketing url
        (CourseRunStatus.Published, True, True, True),  # Published, seats, marketing url
    )
    @ddt.unpack
    def test_is_marketable(self, status, create_seats, create_marketing_url, expected):
        course_run = factories.CourseRunFactory.create(status=status)
        if not create_marketing_url:
            course_run.slug = None
        if create_seats:
            factories.SeatFactory.create(course_run=course_run)

        self.assertEqual(course_run.is_marketable, expected)

    @ddt.data(
        (True, False, False),  # Draft, CourseRunType.is_marketable, expected
        (True, True, False),
        (False, False, False),
        (False, True, True),
    )
    @ddt.unpack
    def test_could_be_marketable(self, draft, type_is_marketable, expected):
        course_run = factories.CourseRunFactory(status=CourseRunStatus.Published, draft=draft,
                                                type__is_marketable=type_is_marketable)
        factories.SeatFactory.create(course_run=course_run)
        self.assertEqual(course_run.is_marketable, expected)
        self.assertEqual(course_run.could_be_marketable, expected)

        with mock.patch.object(CourseRunMarketingSitePublisher, 'publish_obj', return_value=None) as mock_publish_obj:
            with override_switch('publish_course_runs_to_marketing_site', True):
                course_run.save()
                self.assertEqual(mock_publish_obj.called, expected)


class CourseRunTestsThatNeedSetUp(OAuth2Mixin, TestCase):
    """
    Tests for the `CourseRun` model where the course_run fixture object
    REALLY needs to be re-created before each test.
    """

    def setUp(self):
        super().setUp()
        subject = factories.SubjectFactory()
        self.course_run = factories.CourseRunFactory(course__subjects=[subject])
        self.partner = self.course_run.course.partner

    def mock_ecommerce_publication(self):
        url = '{root}publication/'.format(root=self.partner.ecommerce_api_url)
        responses.add(responses.POST, url, json={}, status=200)

    def test_official_created(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()

        self.course_run.draft = True
        self.course_run.status = CourseRunStatus.Reviewed
        self.course_run.course.draft = True
        factories.SeatFactory(course_run=self.course_run, draft=True)
        # We have to specify a SeatType that exists in Seat.ENTITLEMENT_MODES in order for the
        # official version of the Entitlement to be created
        entitlement_mode = SeatTypeFactory.verified()
        factories.CourseEntitlementFactory(course=self.course_run.course, mode=entitlement_mode, draft=True)
        self.course_run.course.save()
        self.course_run.save()
        assert CourseRun.everything.all().count() == 2
        official_run = CourseRun.everything.get(key=self.course_run.key, draft=False)
        draft_run = CourseRun.everything.get(key=self.course_run.key, draft=True)

        assert official_run.draft_version == draft_run
        assert official_run != draft_run
        assert official_run.slug == draft_run.slug

        assert official_run.course.draft is False
        assert official_run.course.draft_version == draft_run.course
        assert official_run.course != draft_run.course
        assert official_run.course.slug == draft_run.course.slug

        official_entitlement = official_run.course.entitlements.first()
        draft_entitlement = draft_run.course.entitlements.first()
        assert official_entitlement.draft_version == draft_entitlement
        assert official_entitlement.draft is False
        assert draft_entitlement.draft is True
        assert official_entitlement != draft_entitlement

        official_seat = official_run.seats.first()
        draft_seat = draft_run.seats.first()
        assert official_seat.draft_version == draft_seat
        assert official_seat.draft is False
        assert draft_seat.draft is True
        assert official_seat != draft_seat

    def test_official_canonical_updates_to_official(self):
        self.course_run.draft = True
        self.course_run.status = CourseRunStatus.Reviewed
        self.course_run.course.draft = True
        self.course_run.course.save()
        self.course_run.save()

        official_run = CourseRun.everything.get(key=self.course_run.key, draft=False)
        assert official_run.course.canonical_course_run == official_run

        draft_run = CourseRun.everything.get(key=self.course_run.key, draft=True)
        assert draft_run.course.canonical_course_run == draft_run

    def test_canonical_becomes_first_reviewed(self):
        course = factories.CourseFactory(draft=True)
        (run_a, run_b) = tuple(factories.CourseRunFactory.create_batch(2, course=course, draft=True))
        course.canonical_course_run = run_a
        run_b.status = CourseRunStatus.Reviewed
        course.save()
        run_a.save()
        run_b.save()

        draft_run_b = CourseRun.everything.get(key=run_b.key, draft=True)
        assert draft_run_b.course.canonical_course_run == draft_run_b

        official_run_b = CourseRun.everything.get(key=run_b.key, draft=False)
        assert official_run_b.course.canonical_course_run == official_run_b

    def test_no_duplicate_official(self):
        self.course_run.course.draft = True
        self.course_run.course.save()
        official_course = factories.CourseFactory.create(partner=self.course_run.course.partner)
        official_course.draft_version = self.course_run.course
        official_course.save()

        self.course_run.draft = True
        official_version = factories.CourseRunFactory.create(course=official_course, status=CourseRunStatus.Unpublished)
        official_version.draft_version = self.course_run
        official_version.save()

        self.course_run.status = CourseRunStatus.Reviewed
        self.course_run.save()
        assert CourseRun.everything.all().count() == 2
        assert Course.everything.all().count() == 2

    def test_publication_disabled(self):
        """
        Verify that the publisher is not initialized when publication is disabled.
        """
        with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
            self.course_run.save()
            self.course_run.delete()

            assert mock_init.call_count == 0

        with override_switch('publish_course_runs_to_marketing_site', True):
            with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
                # Make sure if the save comes from refresh_course_metadata, we don't actually publish
                self.course_run.save(suppress_publication=True)
                assert mock_init.call_count == 0

            self.partner.marketing_site_url_root = ''
            self.partner.save()

            with mock.patch.object(CourseRunMarketingSitePublisher, '__init__') as mock_init:
                self.course_run.save()
                self.course_run.delete()

                assert mock_init.call_count == 0

    @override_switch('publish_course_runs_to_marketing_site', True)
    def test_publication_enabled(self):
        """
        Verify that the publisher is called when publication is enabled.
        """
        with mock.patch.object(CourseRunMarketingSitePublisher, 'publish_obj', return_value=None) as mock_publish_obj:
            self.course_run.save()
            assert mock_publish_obj.called

        with mock.patch.object(CourseRunMarketingSitePublisher, 'delete_obj', return_value=None) as mock_delete_obj:
            self.course_run.delete()
            # We don't want to delete course run nodes when CourseRuns are deleted.
            assert not mock_delete_obj.called

    def test_push_tracks_to_lms(self):
        """
        Verify that we notify the LMS about tracks without seats on a save() to reviewed
        """
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.partner.save()
        self.mock_access_token()
        self.mock_ecommerce_publication()
        url = '{root}courses/{key}/'.format(root=self.partner.lms_coursemode_api_url, key=self.course_run.key)

        # Mark course as draft
        self.course_run.course.draft = True
        self.course_run.course.save()

        # Set up and save run
        self.course_run.type = factories.CourseRunTypeFactory(
            tracks=[
                factories.TrackFactory(mode__slug='no-seat', seat_type=None),
                factories.TrackFactory(mode__slug='has-seat'),
            ],
        )
        self.course_run.draft = True
        self.course_run.status = CourseRunStatus.Reviewed

        responses.add(responses.GET, url, json=[], status=200)
        responses.add(responses.POST, url, json={}, status=201)
        with LogCapture(utils_logger.name) as log_capture:
            self.course_run.save()
            log_capture.check_present((utils_logger.name, 'INFO',
                                      'Successfully published [no-seat] LMS mode for [%s].' % self.course_run.key))

        # Test that we don't re-publish modes
        self.course_run.status = CourseRunStatus.Unpublished
        self.course_run.save()
        self.course_run.status = CourseRunStatus.Reviewed
        responses.replace(responses.GET, url, json=[{'mode_slug': 'no-seat'}], status=200)
        with LogCapture(utils_logger.name) as log_capture:
            self.course_run.save()
            log_capture.check()  # no messages at all, we skipped sending

        # Test we report failures
        self.course_run.status = CourseRunStatus.Unpublished
        self.course_run.save()
        self.course_run.status = CourseRunStatus.Reviewed
        responses.replace(responses.GET, url, json=[], status=200)
        responses.replace(responses.POST, url, body='Shrug', status=500)
        with LogCapture(utils_logger.name) as log_capture:
            self.course_run.save()
            log_capture.check_present((utils_logger.name, 'WARNING',
                                      'Failed publishing [no-seat] LMS mode for [%s]: Shrug' % self.course_run.key))

    def test_verified_seat_upgrade_deadline_override(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()

        self.course_run.draft = True
        self.course_run.status = CourseRunStatus.Reviewed
        self.course_run.course.draft = True
        upgrade_deadline = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10)
        verified_type = SeatTypeFactory.verified()
        factories.SeatFactory(
            course_run=self.course_run,
            draft=True,
            type=verified_type,
            upgrade_deadline=upgrade_deadline
        )

        factories.CourseEntitlementFactory(course=self.course_run.course, mode=verified_type, draft=True)
        self.course_run.course.save()
        self.course_run.save()
        draft_seat = Seat.everything.get(course_run=self.course_run, draft=True, type=verified_type)
        official_run = CourseRun.everything.get(key=self.course_run.key, draft=False)
        official_seat = Seat.everything.get(course_run=official_run, draft=False, type=verified_type)

        assert draft_seat.upgrade_deadline == upgrade_deadline
        assert official_seat.upgrade_deadline == upgrade_deadline

        # Simulate updating the draft seat in Django admin which is how we currently support changing it
        new_deadline = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=15)
        draft_seat.upgrade_deadline = new_deadline
        draft_seat.save()

        draft_run = CourseRun.everything.get(key=self.course_run.key, draft=True)
        draft_run.update_or_create_official_version()

        draft_seat = Seat.everything.get(course_run=self.course_run, draft=True, type=verified_type)
        official_seat = Seat.everything.get(course_run=official_run, draft=False, type=verified_type)
        assert draft_run.seats.get(type=verified_type).upgrade_deadline == new_deadline
        assert official_run.seats.get(type=verified_type).upgrade_deadline == new_deadline


@ddt.ddt
class OrganizationTests(TestCase):
    """ Tests for the `Organization` model. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organization = factories.OrganizationFactory()
        cls._original_org_key = cls.organization.key

    def setUp(self):
        super().setUp()
        self.organization.key = self._original_org_key

    @ddt.data(
        [" ", ",", "@", "(", "!", "#", "$", "%", "^", "&", "*", "+", "=", "{", "[", "ó"]
    )
    def test_clean_error(self, invalid_char_list):
        """
        Verify that the clean method raises validation error if key consists of special characters
        """
        for char in invalid_char_list:
            self.organization.key = 'key{}'.format(char)
            self.assertRaises(ValidationError, self.organization.clean)

    @ddt.data(
        ["keywithoutspace", "correct-key", "correct_key", "correct.key"]
    )
    def test_clean_success(self, valid_key_list):
        """
        Verify that the clean method returns None if key is valid
        """
        for valid_key in valid_key_list:
            self.organization.key = valid_key
            self.assertEqual(self.organization.clean(), None)

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and name. """
        self.assertEqual(str(self.organization), '{key}: {name}'.format(key=self.organization.key,
                                                                        name=self.organization.name))

    def test_marketing_url(self):
        """ Verify the property creates a complete marketing URL. """
        expected = '{root}/school/{slug}'.format(root=self.organization.partner.marketing_site_url_root.strip('/'),
                                                 slug=self.organization.slug)
        self.assertEqual(self.organization.marketing_url, expected)

    def test_marketing_url_without_slug(self):
        """ Verify the property returns None if the Organization has no slug set. """
        self.organization.slug = ''
        self.assertIsNone(self.organization.marketing_url)

    def test_user_organizations(self):
        """Verify that the user_organizations method returns organizations for a given user"""
        user = factories.UserFactory()

        self.assertFalse(Organization.user_organizations(user))

        org_ext = OrganizationExtensionFactory()
        user.groups.add(org_ext.group)

        assert len(Organization.user_organizations(user)) == 1


@ddt.ddt
class PersonTests(TestCase):
    """ Tests for the `Person` model. """

    def setUp(self):
        super(PersonTests, self).setUp()
        self.person = factories.PersonFactory()

    def test_full_name(self):
        """ Verify the property returns the person's full name. """
        expected = self.person.given_name + ' ' + self.person.family_name
        self.assertEqual(self.person.full_name, expected)

    def test_full_name_with_salutation(self):
        """ Verify the property returns the person's full name
        with salutation.
        """
        self.person = factories.PersonFactory(salutation='Dr.')
        expected = ' '.join((self.person.salutation, self.person.given_name, self.person.family_name))
        self.assertEqual(self.person.full_name, expected)

    def test_empty_family_name(self):
        """ Verify the property returns the person's given name when family name is set None. """
        self.person.family_name = None
        expected = self.person.given_name
        self.assertEqual(self.person.full_name, expected)

    def test_unicode_slug(self):
        """ Verify the slug is reasonable with a unicode name. """
        self.person = factories.PersonFactory(given_name='商汤科', family_name='')
        self.assertEqual(self.person.slug, 'shang-tang-ke')

    def test_get_profile_image_url(self):
        """
        Verify that property returns profile_image_url, which should always be the
        profile_image.url.
        """
        self.assertEqual(self.person.get_profile_image_url, self.person.profile_image.url)

        # create another person with out profile_image_url
        person = factories.PersonFactory()
        self.assertEqual(person.get_profile_image_url, person.profile_image.url)

        # create another person with out profile_image
        person = factories.PersonFactory(profile_image=None)
        self.assertIsNone(person.get_profile_image_url)

    def test_str(self):
        """ Verify casting an instance to a string returns the person's full name. """
        self.assertEqual(str(self.person), self.person.full_name)

    @ddt.data('bio', 'major_works')
    def test_html_fields_are_validated(self, field_name):
        # Happy path
        setattr(self.person, field_name, '<p>')
        self.person.clean_fields()

        # Bad HTML
        setattr(self.person, field_name, '<?proc>')
        with self.assertRaises(ValidationError) as cm:
            self.person.clean_fields()
        self.assertEqual(cm.exception.message_dict[field_name], ['Invalid HTML received'])


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


class AbstractTitleDescriptionModelTests(TestCase):
    """ Tests for AbstractTitleDescriptionModel. """

    def test_str(self):
        class TestAbstractTitleDescriptionModel(AbstractTitleDescriptionModel):
            pass

        title = 'test title'
        description = 'Description'

        instance = TestAbstractTitleDescriptionModel(title=None, description=description)
        self.assertEqual(str(instance), description)

        instance = TestAbstractTitleDescriptionModel(title=title, description=description)
        self.assertEqual(str(instance), title)


@ddt.ddt
class ProgramTests(TestCase):
    """Tests of the Program model."""

    @classmethod
    def setUpClass(cls):
        """
        Creates fixture subjects, course_runs, courses, and programs from factories.
        """
        super(ProgramTests, cls).setUpClass()
        transcript_languages = LanguageTag.objects.all()[:2]
        cls.subjects = factories.SubjectFactory.create_batch(3)
        cls.course_runs = factories.CourseRunFactory.create_batch(
            3, transcript_languages=transcript_languages, course__subjects=cls.subjects,
            weeks_to_complete=2)
        cls.courses = [course_run.course for course_run in cls.course_runs]
        cls.excluded_course_run = factories.CourseRunFactory(course=cls.courses[0])
        cls.program = factories.ProgramFactory(courses=cls.courses, excluded_course_runs=[cls.excluded_course_run])

        cls.other_course_run = factories.CourseRunFactory()
        cls.other_program = factories.ProgramFactory(courses=[cls.other_course_run.course])

    def tearDown(self):
        """
        Resets course canonical_course_runs to initial state.
        """
        super(ProgramTests, self).tearDown()
        for course_run in self.course_runs[:2]:
            course = course_run.course
            course.canonical_course_run = None
            course.save()

    # pylint: disable=access-member-before-definition, attribute-defined-outside-init
    def create_program_with_seats(self):
        if getattr(self, '__program_with_seats', None):
            return self.__program_with_seats

        currency = Currency.objects.get(code='USD')

        course_run = factories.CourseRunFactory()
        course_run.course.canonical_course_run = course_run
        course_run.course.save()
        audit_seat_type = factories.SeatTypeFactory.audit()
        credit_seat_type = factories.SeatTypeFactory.credit()
        verified_seat_type = factories.SeatTypeFactory.verified()
        factories.SeatFactory(type=audit_seat_type, currency=currency, course_run=course_run, price=0)
        factories.SeatFactory(type=credit_seat_type, currency=currency, course_run=course_run, price=600)
        factories.SeatFactory(type=verified_seat_type, currency=currency, course_run=course_run, price=100)

        program_type = factories.ProgramTypeFactory(applicable_seat_types=[credit_seat_type, verified_seat_type])

        self.__program_with_seats = factories.ProgramFactory(type=program_type, courses=[course_run.course])
        return self.__program_with_seats

    def test_search(self):
        """
        Verify that the program endpoint correctly handles basic elasticsearch queries
        """
        query = 'title:' + self.program.title
        self.assertSetEqual(set(Program.search(query)), set([self.program]))

    def test_subject_search(self):
        """
        Verify that the program endpoint correctly handles elasticsearch queries on the subject uuid
        """
        query = str(self.subjects[0].uuid)
        self.assertSetEqual(set(Program.search(query)), set([self.program]))

    # pylint: disable=access-member-before-definition, attribute-defined-outside-init
    def create_program_with_entitlements_and_seats(self):
        if getattr(self, '__entitlements_program_and_courses', None):
            return self.__entitlements_program_and_courses

        verified_seat_type = SeatTypeFactory.verified()
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])
        courses = []
        for __ in range(3):
            entitlement = factories.CourseEntitlementFactory(mode=verified_seat_type)
            for __ in range(3):
                factories.SeatFactory(
                    course_run=factories.CourseRunFactory(
                        end=None,
                        enrollment_end=None,
                        course=entitlement.course
                    ),
                    type=verified_seat_type, upgrade_deadline=None
                )
            courses.append(entitlement.course)

        program = factories.ProgramFactory(
            courses=courses,
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.__entitlements_program_and_courses = (program, courses)
        return program, courses

    def assert_one_click_purchase_ineligible_program(
            self, end=None, enrollment_start=None, enrollment_end=None, seat_type=None,
            upgrade_deadline=None, one_click_purchase_enabled=True, excluded_course_runs=None, program_type=None
    ):
        course_run = factories.CourseRunFactory(
            end=end, enrollment_start=enrollment_start, enrollment_end=enrollment_end
        )
        seat_type = seat_type or SeatTypeFactory.verified()
        factories.SeatFactory(course_run=course_run, type=seat_type, upgrade_deadline=upgrade_deadline)
        program = factories.ProgramFactory(
            courses=[course_run.course],
            excluded_course_runs=excluded_course_runs,
            one_click_purchase_enabled=one_click_purchase_enabled,
            type=program_type,
        )
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

    def test_clean_enrollment_counts_on_save(self):
        """ Verify that the 'clean' method ensures that we don't save NULL counts to DB """
        course_run = factories.CourseRunFactory()

        course_run.enrollment_count = None
        course_run.recent_enrollment_count = None
        course_run.clean()
        course_run.save()
        course_run_from_db = CourseRun.objects.get(uuid=course_run.uuid)
        self.assertEqual(0, course_run_from_db.enrollment_count)
        self.assertEqual(0, course_run_from_db.recent_enrollment_count)

        course_run.enrollment_count = 3
        course_run.recent_enrollment_count = 2
        course_run.clean()
        course_run.save()
        course_run_from_db = CourseRun.objects.get(uuid=course_run.uuid)
        self.assertEqual(3, course_run_from_db.enrollment_count)
        self.assertEqual(2, course_run_from_db.recent_enrollment_count)

        course = course_run.course
        course.enrollment_count = None
        course.recent_enrollment_count = None
        course.clean()
        course.save()
        course_from_db = Course.objects.get(uuid=course.uuid)
        self.assertEqual(0, course_from_db.enrollment_count)
        self.assertEqual(0, course_from_db.recent_enrollment_count)

        course.enrollment_count = 4
        course.recent_enrollment_count = 5
        course.clean()
        course.save()
        course_from_db = Course.objects.get(uuid=course.uuid)
        self.assertEqual(4, course_from_db.enrollment_count)
        self.assertEqual(5, course_from_db.recent_enrollment_count)

        program = factories.ProgramFactory(courses=[course])
        program.enrollment_count = None
        program.recent_enrollment_count = None
        program.clean()
        program.save()

        program_from_db = Program.objects.get(uuid=program.uuid)
        self.assertEqual(0, program_from_db.enrollment_count)
        self.assertEqual(0, program_from_db.recent_enrollment_count)

    def test_one_click_purchase_eligible(self):
        """ Verify that program is one click purchase eligible. """
        verified_seat_type = SeatTypeFactory.verified()
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
            factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
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
        factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
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

    def test_one_click_purchase_eligible_with_entitlements(self):
        """ Verify that program is one click purchase eligible when its courses have entitlement products. """
        # Program has one_click_purchase_enabled set to True,
        # all courses have a verified mode entitlement product and multiple course runs.
        program, __ = self.create_program_with_entitlements_and_seats()
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_ineligible_wrong_mode(self):
        """ Verify that program is not one click purchase eligible if course entitlement product has the wrong mode. """
        program, courses = self.create_program_with_entitlements_and_seats()
        honor_seat_type = SeatTypeFactory.honor()
        honor_mode_entitlement = courses[0].entitlements.first()
        original_mode = honor_mode_entitlement.mode
        honor_mode_entitlement.mode = honor_seat_type
        honor_mode_entitlement.save()
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

        # clean up local modifications
        honor_mode_entitlement.mode = original_mode
        honor_mode_entitlement.mode.save()

    def test_one_click_purchase_ineligible_multiple_entitlements(self):
        """
        Verify that program is not one click purchase eligible if course has
        multiple entitlement products with correct modes.
        """
        program, courses = self.create_program_with_entitlements_and_seats()
        credit_seat_type = SeatTypeFactory.credit()
        program.type.applicable_seat_types.add(credit_seat_type)
        # We are limiting each course to a single entitlement so this should raise an IntegrityError
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                factories.CourseEntitlementFactory(mode=credit_seat_type, course=courses[0])

    def test_one_click_purchase_eligible_with_unpublished_runs(self):
        """ Verify that program with unpublished course runs is one click purchase eligible. """

        verified_seat_type = SeatTypeFactory.verified()
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
        factories.SeatFactory(course_run=published_course_run, type=verified_seat_type, upgrade_deadline=None)
        factories.SeatFactory(course_run=unpublished_course_run, type=verified_seat_type, upgrade_deadline=None)
        program = factories.ProgramFactory(
            courses=[published_course_run.course],
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_ineligible(self):
        """ Verify that program is one click purchase ineligible. """
        yesterday = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        tomorrow = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        verified_seat_type = SeatTypeFactory.verified()
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
        second_course_run = factories.CourseRunFactory(end=None, enrollment_end=None, course=course_run.course)
        factories.SeatFactory(course_run=course_run, type=verified_seat_type, upgrade_deadline=None)
        program = factories.ProgramFactory(
            courses=[course_run.course],
            one_click_purchase_enabled=True,
            type=program_type,
        )
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

        # Program has one_click_purchase_enabled set to True and
        # one course with one course run excluded from the program
        second_course_run.delete()
        program.excluded_course_runs.set([course_run])
        program.save()
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
            seat_type=SeatTypeFactory.credit(),
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
        Verify that we only fetch course runs for the program, and not other course runs for other programs.
        Also verify that the property returns the set of associated
        CourseRuns minus those that are explicitly excluded.
        """
        # Verify that self.other_course_run is not returned in set
        self.assertEqual(set(self.program.course_runs), set(self.course_runs))

    def test_canonical_course_runs(self):
        for course_run in self.course_runs[:2]:
            course = course_run.course
            course.canonical_course_run = course_run
            course.save()

        expected_canonical_runs = [self.course_runs[0], self.course_runs[1]]
        # Verify only canonical course runs are returned in set
        self.assertEqual(set(self.program.canonical_course_runs), set(expected_canonical_runs))

    def test_canonical_course_seats(self):
        """ Test canonical course seats returns only canonical course run's applicable seats """
        currency = Currency.objects.get(code='USD')

        course = factories.CourseFactory()
        course_runs_same_course = factories.CourseRunFactory.create_batch(3, course=course)
        verified_seat_type = factories.SeatTypeFactory.verified()
        for course_run in course_runs_same_course:
            factories.SeatFactory(type=verified_seat_type, currency=currency, course_run=course_run, price=100)
        course.canonical_course_run = course_runs_same_course[0]
        course.save()

        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])

        program = factories.ProgramFactory(type=program_type, courses=[course])

        self.assertEqual(set(course.canonical_course_run.seats.all()), set(program.canonical_seats))

    def test_entitlements(self):
        """ Test entitlements returns only applicable course entitlements. """
        courses = factories.CourseFactory.create_batch(3)
        verified_type = factories.SeatTypeFactory.verified()
        credit_type = factories.SeatTypeFactory.credit()
        professional_type = factories.SeatTypeFactory.professional()
        for i, mode in enumerate([verified_type, credit_type, professional_type]):
            factories.CourseEntitlementFactory(course=courses[i], mode=mode)
        applicable_seat_types = [verified_type, professional_type]
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        program = factories.ProgramFactory(type=program_type, courses=courses)
        expected = {c.entitlements.filter(mode__in=applicable_seat_types).first() for c in courses}
        expected.remove(None)
        self.assertEqual(expected, set(program.entitlements))

    def test_languages(self):
        expected_languages = {course_run.language for course_run in self.course_runs}
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

    def test_subject_order(self):
        """
        Verify the program's subjects are in order of frequency among courses, with primary subjects coming first
        """
        course1 = factories.CourseFactory(subjects=self.subjects[:1])  # A
        course2 = factories.CourseFactory(subjects=self.subjects[:2])  # A, B
        course3 = factories.CourseFactory(subjects=self.subjects[::-1])  # C, B, A

        program1 = factories.ProgramFactory(courses=[course1, course2, course3])
        self.assertEqual(program1.subjects, self.subjects)

        course4 = factories.CourseFactory(subjects=self.subjects[::-2])  # C, A; these make C the most common primary
        course5 = factories.CourseFactory(subjects=self.subjects[::-2])  # C, A; and A the most common overall in p2
        program2 = factories.ProgramFactory(courses=[course1, course2, course3, course4, course5])
        self.assertEqual(program2.subjects, [self.subjects[2], self.subjects[0], self.subjects[1]])

    def test_program_topics(self):
        """
        Verify the program aggregates its courses' topic tags
        """
        topicA = Tag.objects.create(name="topicA")
        topicB = Tag.objects.create(name="topicB")
        topicC = Tag.objects.create(name="topicC")

        course1 = factories.CourseFactory()
        course1.topics.set(topicA)
        course2 = factories.CourseFactory()
        course2.topics.set(topicA, topicB)
        course3 = factories.CourseFactory()
        course3.topics.set(topicB, topicC)

        program1 = factories.ProgramFactory(courses=[course1, course2, course3])
        self.assertEqual(program1.topics, set((topicA, topicB, topicC)))

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
        audit_seat_type = factories.SeatTypeFactory.audit()
        verified_seat_type = factories.SeatTypeFactory.verified()
        for course_run in self.course_runs:
            factories.SeatFactory(type=audit_seat_type, currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(type=verified_seat_type, currency=currency, course_run=course_run, price=test_price)
            test_price += 100
            course_run.course.canonical_course_run = course_run
            course_run.course.save()

        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])

        self.program.type = program_type

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(100), 'max': Decimal(300), 'total': Decimal(600)}]
        self.assertEqual(self.program.price_ranges, expected_price_ranges)

    @ddt.data(True, False)
    def test_price_ranges_with_entitlements(self, create_seats):
        """ Verifies the price_range property of a program with course entitlement products """
        currency = Currency.objects.get(code='USD')
        test_price = 100
        verified_type = SeatTypeFactory.verified()
        for course_run in self.course_runs:
            factories.CourseEntitlementFactory(
                currency=currency, course=course_run.course, price=test_price, mode=verified_type
            )
            if create_seats:
                factories.SeatFactory(type=verified_type, currency=currency, price=test_price, course_run=course_run)
            course_run.course.canonical_course_run = course_run
            course_run.course.save()
            test_price += 100

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
        audit_seat_type = factories.SeatTypeFactory.audit()
        verified_seat_type = factories.SeatTypeFactory.verified()
        for course_run in single_course_course_runs:
            factories.SeatFactory(type=audit_seat_type, currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(type=verified_seat_type, currency=currency, course_run=course_run, price=10)
            course_run.course.canonical_course_run = course_run
            course_run.course.save()

        day_separation = 1
        now = datetime.datetime.now(pytz.UTC)

        for course_run in course_runs_same_course:
            if set_all_dates or day_separation < 2:
                date_delta = datetime.timedelta(days=day_separation)
                course_run.enrollment_start = now - date_delta
                course_run.end = now + datetime.timedelta(weeks=day_separation)
            else:
                course_run.enrollment_start = None
                course_run.end = None
            course_run.save()
            factories.SeatFactory(type=audit_seat_type, currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(
                type=verified_seat_type,
                currency=currency,
                course_run=course_run,
                price=(day_separation * 100))
            day_separation += 1
        course.canonical_course_run = course_runs_same_course[2]
        course.save()
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])

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
        TWO_WEEKS_FROM_TODAY = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=14)
        YESTERDAY = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        TOMORROW = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        expected_staff = factories.PersonFactory.create_batch(2)
        unexpected_staff = factories.PersonFactory.create_batch(2)
        advertised_course_run = factories.CourseRunFactory(
            start=YESTERDAY,
            end=TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Published,
            enrollment_end=TWO_WEEKS_FROM_TODAY,
            staff=set(expected_staff)
        )
        SeatFactory(
            course_run=advertised_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=TOMORROW
        )
        ignored_course_run = factories.CourseRunFactory(
            status=CourseRunStatus.Unpublished,
            staff=set(unexpected_staff)
        )
        self.program.courses.set([advertised_course_run.course, ignored_course_run.course])

        self.assertEqual(self.program.staff, set(expected_staff))

    def test_staff_no_advertised_course_run(self):
        staff = factories.PersonFactory.create_batch(2)
        self.course_runs[0].staff.add(staff[0])
        self.course_runs[1].staff.add(staff[1])

        self.assertEqual(self.program.staff, set())

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
        self.assertEqual({t.slug for t in program.seat_types}, {Seat.CREDIT, Seat.VERIFIED})

    @ddt.data(ProgramStatus.choices)
    def test_is_active(self, status):
        self.program.status = status
        self.assertEqual(self.program.is_active, status == ProgramStatus.Active)

    def test_publication_disabled(self):
        """
        Verify that the publisher is not initialized when publication is disabled.
        """
        program = factories.ProgramFactory()
        with mock.patch.object(ProgramMarketingSitePublisher, '__init__') as mock_init:
            program.save()
            program.delete()

            assert mock_init.call_count == 0

        with override_switch('publish_program_to_marketing_site', True):
            program.partner.marketing_site_url_root = ''
            program.partner.save()

            with mock.patch.object(ProgramMarketingSitePublisher, '__init__') as mock_init:
                program.save()
                program.delete()

                assert mock_init.call_count == 0

    @override_switch('publish_program_to_marketing_site', True)
    def test_publication_enabled(self):
        """
        Verify that the publisher is called when publication is enabled.
        """
        program = factories.ProgramFactory()
        with mock.patch.object(ProgramMarketingSitePublisher, 'publish_obj', return_value=None) as mock_publish_obj:
            program.save()
            assert mock_publish_obj.called

        with mock.patch.object(ProgramMarketingSitePublisher, 'delete_obj', return_value=None) as mock_delete_obj:
            program.delete()
            assert mock_delete_obj.called

    def test_credit_value(self):
        """
        Verify that we can set the credit_value field on a program
        """
        course_run = factories.CourseRunFactory()
        program = factories.ProgramFactory(courses=[course_run.course])
        program.credit_value = 1
        program.clean()
        program.save()

        program_from_db = Program.objects.get(uuid=program.uuid)
        self.assertEqual(1, program_from_db.credit_value)


class PathwayTests(TestCase):
    """ Tests of the Pathway model."""

    def test_str(self):
        pathway = factories.PathwayFactory()
        self.assertEqual(str(pathway), pathway.name)


class PersonSocialNetworkTests(TestCase):
    """Tests of the PersonSocialNetwork model."""

    def setUp(self):
        super(PersonSocialNetworkTests, self).setUp()
        self.network = factories.PersonSocialNetworkFactory()
        self.person = factories.PersonFactory()

    def test_str(self):
        """Verify that a person-social-network is properly converted to a str."""
        self.assertEqual(
            str(self.network), '{title}: {url}'.format(title=self.network.display_title, url=self.network.url)
        )

    def test_unique_constraint(self):
        """Verify that a person-social-network does not allow multiple accounts for same
        social network.
        """
        factories.PersonSocialNetworkFactory(person=self.person, type='facebook', title='@Mikix')
        with self.assertRaises(IntegrityError):
            factories.PersonSocialNetworkFactory(person=self.person, type='facebook', title='@Mikix')


class PersonAreaOfExpertiseTests(TestCase):
    """Tests for the PersonAreaOfExpertise model."""

    def setUp(self):
        super(PersonAreaOfExpertiseTests, self).setUp()
        self.area_of_expertise = factories.PersonAreaOfExpertiseFactory()

    def test_str(self):
        self.assertEqual(str(self.area_of_expertise), self.area_of_expertise.value)


class SeatTypeTests(TestCase):
    """ Tests of the SeatType model. """

    def test_str(self):
        seat_type = factories.SeatTypeFactory()
        self.assertEqual(str(seat_type), seat_type.name)


class ProgramTypeTests(TestCase):
    """ Tests of the ProgramType model. """

    def test_str(self):
        program_type = factories.ProgramTypeFactory()
        self.assertEqual(str(program_type), program_type.name_t)


class CourseEntitlementTests(TestCase):
    """ Tests of the CourseEntitlement model. """

    def setUp(self):
        super(CourseEntitlementTests, self).setUp()
        self.course = factories.CourseFactory()
        self.mode = factories.SeatTypeFactory()

    def test_unique_constraint(self):
        """
        Verify that a CourseEntitlement does not allow multiple skus or prices for the same course and mode.
        """
        factories.CourseEntitlementFactory(course=self.course, mode=self.mode)
        with self.assertRaises(IntegrityError):
            factories.CourseEntitlementFactory(course=self.course, mode=self.mode)


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


class RankingTests(TestCase):
    """ Tests of the Ranking model. """

    def test_str(self):
        description = 'test rank'
        ranking = Ranking.objects.create(rank='#1', description=description, source='test')
        self.assertEqual(str(ranking), description)


@ddt.ddt
class CurriculumTests(TestCase):
    """ Tests of the Curriculum model. """
    def setUp(self):
        super().setUp()
        self.course_run = factories.CourseRunFactory()
        self.courses = [self.course_run.course]
        self.degree = factories.DegreeFactory(courses=self.courses)
        self.curriculum = Curriculum(program=self.degree)

    def test_str(self):
        self.assertEqual(str(self.curriculum), str(self.curriculum.uuid))

    @ddt.data('marketing_text', 'marketing_text_brief')
    def test_html_fields_are_validated(self, field_name):
        # marketing_text is blank=False, so always provide something here
        self.curriculum.marketing_text = '<p>'

        # Happy path
        setattr(self.curriculum, field_name, '<p>')
        self.curriculum.clean_fields()

        # Bad HTML
        setattr(self.curriculum, field_name, '<?proc>')
        with self.assertRaises(ValidationError) as cm:
            self.curriculum.clean_fields()
        self.assertEqual(cm.exception.message_dict[field_name], ['Invalid HTML received'])


class CurriculumProgramMembershipTests(TestCase):
    """ Tests of the CurriculumProgramMembership model. """
    def setUp(self):
        super().setUp()
        self.course_run = factories.CourseRunFactory()
        self.degree = factories.DegreeFactory()
        self.program = factories.ProgramFactory(courses=[self.course_run.course])
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())

    def test_program_unique_within_same_curriculum(self):
        CurriculumProgramMembership.objects.create(
            program=self.program,
            curriculum=self.curriculum
        )
        # Add the same program curriculum relationship again.
        # Make sure this throws db integrity exception
        with self.assertRaises(IntegrityError):
            CurriculumProgramMembership.objects.create(
                program=self.program,
                curriculum=self.curriculum
            )

    def test_same_program_added_to_different_curriculum(self):
        CurriculumProgramMembership.objects.create(
            program=self.program,
            curriculum=self.curriculum
        )
        new_curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())
        CurriculumProgramMembership.objects.create(
            program=self.program,
            curriculum=new_curriculum
        )
        self.assertEqual(
            self.curriculum.program_curriculum.all()[0],
            new_curriculum.program_curriculum.all()[0]
        )


class CurriculumCourseMembershipTests(TestCase):
    """ Tests of the CurriculumCourseMembership model. """
    def setUp(self):
        super().setUp()
        self.course_run = factories.CourseRunFactory()
        self.course = self.course_run.course
        self.degree = factories.DegreeFactory(courses=[self.course])
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())

    def test_course_run_exclusions(self):
        course_runs = factories.CourseRunFactory.create_batch(4, course=self.course)
        course_runs.append(self.course_run)
        course_membership = CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )
        CurriculumCourseRunExclusion.objects.create(
            course_membership=course_membership,
            course_run=course_runs[0]
        )
        CurriculumCourseRunExclusion.objects.create(
            course_membership=course_membership,
            course_run=course_runs[1]
        )
        self.assertEqual(course_membership.course_runs, set(course_runs[2:]))
        self.assertIn(str(self.curriculum), str(course_membership))
        self.assertIn(str(self.course), str(course_membership))

    def test_course_unique_within_same_curriculum(self):
        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )
        # Add the same course curriculum relationship again.
        # Make sure this throws db integrity exception
        with self.assertRaises(IntegrityError):
            CurriculumCourseMembership.objects.create(
                course=self.course,
                curriculum=self.curriculum
            )

    def test_same_course_added_to_different_curriculum(self):
        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )
        new_curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())
        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=new_curriculum
        )
        self.assertEqual(
            self.curriculum.course_curriculum.all()[0],
            new_curriculum.course_curriculum.all()[0]
        )


@ddt.ddt
class DegreeDeadlineTests(TestCase):
    """ Tests the DegreeDeadline model."""
    def setUp(self):
        super().setUp()
        self.course_run = factories.CourseRunFactory()
        self.courses = [self.course_run.course]
        self.degree = factories.DegreeFactory(courses=self.courses)
        self.deadline_name = 'A test deadline'
        self.deadline_date = 'January 1, 2019'

    def test_str(self):
        degree_deadline = DegreeDeadline.objects.create(
            degree=self.degree,
            name=self.deadline_name,
            date=self.deadline_date,
        )
        self.assertEqual(str(degree_deadline), "{} {}".format(self.deadline_name, self.deadline_date))
        self.assertEqual(degree_deadline.time, '')

    @ddt.data('12:30PM EST', '')
    def test_time_field(self, deadline_time):
        degree_deadline = DegreeDeadline.objects.create(
            degree=self.degree,
            name=self.deadline_name,
            date=self.deadline_date,
            time=deadline_time
        )
        self.assertEqual(degree_deadline.time, deadline_time)


class DegreeCostTests(TestCase):
    """ Tests the DegreeCost model."""
    def setUp(self):
        super().setUp()
        self.course_run = factories.CourseRunFactory()
        self.courses = [self.course_run.course]
        self.degree = factories.DegreeFactory(courses=self.courses)

    def test_str(self):
        cost_name = "A test deadline"
        cost_amount = "January 1, 2019"
        degree_cost = DegreeCost.objects.create(
            degree=self.degree,
            description=cost_name,
            amount=cost_amount,
        )
        self.assertEqual(str(degree_cost), str('{}, {}').format(cost_name, cost_amount))


class SubjectTests(SiteMixin, TestCase):
    """ Tests of the Multilingual Subject (and SubjectTranslation) model. """

    def test_validate_unique(self):
        subject = Subject.objects.create(
            name="name1",
            partner_id=self.partner.id,
            banner_image_url="http://www.example.com",
            card_image_url="http://www.example.com")
        self.assertIsNone(subject.full_clean())

        duplicate_subject = Subject(
            name="name1",
            partner_id=self.partner.id,
            banner_image_url="http://www.example.com",
            card_image_url="http://www.example.com")

        with self.assertRaises(ValidationError) as validation_error:
            duplicate_subject.full_clean()
        self.assertEqual(
            str(validation_error.exception),
            "{'name': ['Subject with this Name and Partner already exists']}")


class TopicTests(SiteMixin, TestCase):
    """ Tests of the Multilingual Topic (and TopicTranslation) model. """

    def test_validate_unique(self):
        topic = Topic.objects.create(
            name="name1",
            partner_id=self.partner.id,
            banner_image_url="http://www.example.com",
        )
        self.assertIsNone(topic.full_clean())

        duplicate_topic = Topic(
            name="name1",
            partner_id=self.partner.id,
            banner_image_url="http://www.example.com",
        )

        with self.assertRaises(ValidationError) as validation_error:
            duplicate_topic.full_clean()
        self.assertEqual(
            str(validation_error.exception),
            "{'name': ['Topic with this Name and Partner already exists']}")

    def test_str(self):
        name = "name"
        topic = Topic.objects.create(name=name, partner_id=self.partner.id)
        self.assertEqual(topic.__str__(), name)


class DegreeTests(TestCase):
    """ Tests of the Degree, Curriculum, and related models. """

    def setUp(self):
        super(DegreeTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.courses = [self.course_run.course]
        self.degree = factories.DegreeFactory(courses=self.courses)
        self.curriculum = factories.CurriculumFactory(program=self.degree)

    def test_basic_degree(self):
        assert self.degree.curricula.exists()
        assert self.curriculum.program_curriculum is not None
        assert self.curriculum.course_curriculum is not None
        assert self.curriculum.marketing_text is not None
        assert self.degree.lead_capture_list_name is not None
        assert self.degree.lead_capture_image is not None
        assert self.degree.campus_image is not None
        assert self.degree.banner_border_color is not None
        assert self.degree.title_background_image is not None
        assert self.degree.micromasters_background_image is not None


class CourseUrlSlugHistoryTest(TestCase):

    def test_slug_with_partner_mismatch(self):
        slug_object = factories.CourseUrlSlugFactory()
        mismatch_partner = factories.PartnerFactory()
        slug_object.partner = mismatch_partner

        with self.assertRaises(ValidationError) as validation_error:
            slug_object.save()
        self.assertEqual(
            validation_error.exception.message_dict['partner'],
            ['Partner {partner_key} and course partner {course_partner_key} do not match when attempting to save url '
             'slug {url_slug}'.format(partner_key=mismatch_partner.name,
                                      course_partner_key=slug_object.course.partner.name,
                                      url_slug=slug_object.url_slug)])
