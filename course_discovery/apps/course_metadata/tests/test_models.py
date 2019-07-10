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
from django.db import IntegrityError
from django.test import TestCase
from freezegun import freeze_time
from taggit.models import Tag

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    FAQ, AbstractMediaModel, AbstractNamedModel, AbstractTitleDescriptionModel, AbstractValueModel,
    CorporateEndorsement, Course, CourseEditor, CourseRun, Curriculum, CurriculumCourseMembership,
    CurriculumCourseRunExclusion, DegreeCost, DegreeDeadline, Endorsement, Program, Ranking, Seat, SeatType, Subject,
    Topic
)
from course_discovery.apps.course_metadata.publishers import (
    CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.tests import factories, toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ImageFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory

# pylint: disable=no-member


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

    @ddt.data('additional_information', 'faq', 'full_description', 'learner_testimonials', 'outcome',
              'prerequisites_raw', 'short_description', 'syllabus_raw')
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
        # Create a seat with 0 price and verify that the course field
        # `first_enrollable_paid_seat_price` returns None
        factories.SeatFactory.create(course_run=course_run, type='verified', price=0, sku='ABCDEF')
        assert course_run.first_enrollable_paid_seat_price is None
        assert course.first_enrollable_paid_seat_price is None

        # Now create a seat with some price and verify that the course field
        # `first_enrollable_paid_seat_price` now returns the price of that
        # payable seat
        factories.SeatFactory.create(course_run=course_run, type='verified', price=100, sku='ABCDEF')
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

    def test_marketing_course_runs(self):
        """
        Verify that only published, non-archived course runs with open
        enrollment, a marketing url, and seats are returned if there is a
        course run with open enrollment.
        """
        course = factories.CourseFactory()
        now = datetime.datetime.now(pytz.UTC)

        unmarketable_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Unpublished,
            end=None,  # Not archived
        )
        unenrollable_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Published,
            enrollment_start=now + datetime.timedelta(days=50),  # Enrollment not started
            end=None,  # Not archived
        )
        archived_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Published,
            end=now - datetime.timedelta(days=100),  # Archived as already ended
        )
        preferred_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Published,
            slug='slug',
            enrollment_start=now - datetime.timedelta(days=50),
            enrollment_end=now + datetime.timedelta(days=100),  # Enrollment still open
            end=None,  # Not archived
        )

        factories.SeatFactory.create(course_run=unmarketable_run)
        factories.SeatFactory.create(course_run=unenrollable_run)
        factories.SeatFactory.create(course_run=archived_run)
        factories.SeatFactory.create(course_run=preferred_run)

        self.assertEqual(course.marketing_course_runs, [preferred_run])

    def test_marketing_course_runs_no_open_enrollment(self):
        """
        Verify that the first published, non-archived course run with a
        marketing url, and seats is returned if there are no runs with open
        enrollment.
        """
        course = factories.CourseFactory()
        now = datetime.datetime.now(pytz.UTC)

        unenrollable_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Published,
            enrollment_start=now + datetime.timedelta(days=50),  # Enrollment not started
            end=now + datetime.timedelta(days=100),  # Not archived
        )
        # Unenrollable run that starts later than the first run
        later_run = factories.CourseRunFactory.create(
            course=course,
            status=CourseRunStatus.Published,
            enrollment_start=now + datetime.timedelta(days=500),  # Enrollment not started even later
            end=now + datetime.timedelta(days=1000),  # Not archived
        )
        factories.SeatFactory.create(course_run=unenrollable_run)
        factories.SeatFactory.create(course_run=later_run)

        self.assertEqual(course.marketing_course_runs, [unenrollable_run])


class TestCourseUpdateMarketingRedirects(MarketingSitePublisherTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.course = factories.CourseFactory()
        self.partner = self.course.partner
        self.past = datetime.datetime(2010, 1, 1, tzinfo=pytz.UTC)
        self.base_args = {'course': self.course, 'status': CourseRunStatus.Published}
        self.active = factories.CourseRunFactory(**self.base_args, end=None, enrollment_end=None)
        self.inactive = factories.CourseRunFactory(**self.base_args, end=self.past)
        self.api_root = self.partner.marketing_site_url_root.rstrip('/')  # overwrite the mixin's version

    def assertRedirect(self, published_runs=None, succeed=True, to_run=None, from_runs=None):
        """
        Args:
            published_runs: Runs to pass to the redirect call
            succeed: Whether the redirect should return True or False
            to_run: A CourseRun that all from_runs are redirected to
            from_runs: An iterable of CourseRuns you expect to be redirected from
        """
        if to_run is None:
            to_run = self.active
        if from_runs is None:
            from_runs = [self.inactive]

        path = 'course_discovery.apps.course_metadata.models.CourseRunMarketingSitePublisher.add_url_redirect'
        with mock.patch(path) as mock_redirect:
            self.assertEqual(self.course.update_marketing_redirects(published_runs=published_runs), succeed)

        if succeed:
            self.assertEqual(mock_redirect.call_count, len(from_runs))
            self.assertEqual({x[0][0] for x in mock_redirect.call_args_list}, {to_run})
            self.assertEqual({x[0][1] for x in mock_redirect.call_args_list}, frozenset(from_runs))

            to_run.refresh_from_db()
            self.assertEqual(to_run.status, CourseRunStatus.Published)  # should have stayed the same

            for from_run in from_runs:
                from_run.refresh_from_db()
                self.assertEqual(from_run.status, CourseRunStatus.Unpublished)
        else:
            self.assertEqual(mock_redirect.call_count, 0)

    def test_simple_happy_path(self):
        self.assertRedirect()

    def test_no_marketing_site(self):
        # Without
        self.partner.marketing_site_url_root = None
        self.partner.save()
        self.assertRedirect(succeed=False)

        # Confirm that with will work
        self.partner.marketing_site_url_root = self.api_root
        self.partner.save()
        self.assertRedirect()

    def test_no_active_runs(self):
        # No active runs returns False
        self.active.status = CourseRunStatus.Unpublished
        self.active.save()
        self.assertRedirect(succeed=False)

        # Confirm that with an active, it will redirect
        self.active.status = CourseRunStatus.Published
        self.active.save()
        self.assertRedirect()

    def test_no_inactive_runs(self):
        # No inactive runs returns False
        self.inactive.status = CourseRunStatus.Unpublished
        self.inactive.save()
        self.assertRedirect(succeed=False)

        # Confirm that with an inactive, it will redirect
        self.inactive.status = CourseRunStatus.Published
        self.inactive.save()
        self.assertRedirect()

    def test_ignores_unpublished(self):
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.Unpublished, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.Reviewed, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.InternalReview, end=self.past)
        factories.CourseRunFactory(course=self.course, status=CourseRunStatus.LegalReview, end=self.past)
        self.assertRedirect()

    def test_multiple_redirects(self):
        inactive2 = factories.CourseRunFactory(**self.base_args, end=self.past)
        self.assertRedirect(from_runs={self.inactive, inactive2})

    def test_earliest_active_run_is_target(self):
        latest = self.active.start
        earlier = latest - datetime.timedelta(days=1)
        earliest = earlier - datetime.timedelta(days=1)
        active2 = factories.CourseRunFactory(**self.base_args, end=None, enrollment_end=None, start=earlier)

        # active2 is earliest
        self.assertRedirect(to_run=active2)

        # Swap which is earlier and confirm we change which we redirect to
        self.inactive.status = CourseRunStatus.Published
        self.inactive.save()
        self.active.start = earliest
        self.active.save()
        self.assertRedirect(to_run=self.active)

    def test_accepts_run_list(self):
        inactive2 = factories.CourseRunFactory(**self.base_args, end=self.past)
        self.assertRedirect(published_runs={self.active, inactive2}, from_runs={inactive2})

    def test_uses_earliest_of_end_or_enrollment_end(self):
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        no_end = factories.CourseRunFactory(**self.base_args, end=None, enrollment_end=self.past)
        no_enrollment_end = factories.CourseRunFactory(**self.base_args, end=self.past, enrollment_end=None)
        earlier_end = factories.CourseRunFactory(**self.base_args, end=self.past, enrollment_end=future)
        earlier_enrollment_end = factories.CourseRunFactory(**self.base_args, end=future, enrollment_end=self.past)
        _in_future = factories.CourseRunFactory(**self.base_args, end=future, enrollment_end=future, start=future)
        self.assertRedirect(from_runs={self.inactive, no_end, no_enrollment_end, earlier_end, earlier_enrollment_end})


class TestCourseEditor(TestCase):
    def setUp(self):
        super().setUp()
        self.user = factories.UserFactory()
        self.courses_qs = Course.objects.all()
        self.runs_qs = CourseRun.objects.all()

        self.org_ext = OrganizationExtensionFactory()
        self.user.groups.add(self.org_ext.group)

        # *** Add a bunch of courses ***

        # Course with no editors
        self.course_no_editors = factories.CourseFactory(title="no editors")
        self.run_no_editors = factories.CourseRunFactory(course=self.course_no_editors)

        # Course with an invalid editor (no group membership)
        bad_editor = factories.UserFactory()
        self.course_bad_editor = factories.CourseFactory(title="bad editor")
        self.run_bad_editor = factories.CourseRunFactory(course=self.course_bad_editor)
        factories.CourseEditorFactory(user=bad_editor, course=self.course_bad_editor)

        # Course with an invalid editor (but course is in our group)
        self.course_bad_editor_in_group = factories.CourseFactory(title="bad editor in group")
        self.course_bad_editor_in_group.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        self.run_bad_editor_in_group = factories.CourseRunFactory(course=self.course_bad_editor_in_group)
        factories.CourseEditorFactory(user=bad_editor, course=self.course_bad_editor_in_group)

        # Course with a valid other editor
        self.good_editor = factories.UserFactory()
        self.good_editor.groups.add(self.org_ext.group)
        self.course_good_editor = factories.CourseFactory(title="good editor")
        self.course_good_editor.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        self.run_good_editor = factories.CourseRunFactory(course=self.course_good_editor)
        factories.CourseEditorFactory(user=self.good_editor, course=self.course_good_editor)

        # Course with user as an invalid editor (no group membership)
        self.course_no_group = factories.CourseFactory(title="no group")
        self.run_no_group = factories.CourseRunFactory(course=self.course_no_group)
        factories.CourseEditorFactory(user=self.user, course=self.course_no_group)

        # Course with user as an valid editor
        self.course_editor = factories.CourseFactory(title="editor")
        self.course_editor.authoring_organizations.add(self.org_ext.organization)  # pylint: disable=no-member
        self.run_editor = factories.CourseRunFactory(course=self.course_editor)
        factories.CourseEditorFactory(user=self.user, course=self.course_editor)

        # Add another authoring_org, which will cause django to return duplicates, if we don't filter them out
        org_ext2 = OrganizationExtensionFactory()
        self.user.groups.add(org_ext2.group)
        self.course_editor.authoring_organizations.add(org_ext2.organization)  # pylint: disable=no-member
        self.course_bad_editor_in_group.authoring_organizations.add(org_ext2.organization)  # pylint: disable=no-member

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

    def test_course_editors_when_valid_editors(self):
        self.assertResultsEqual(partial(CourseEditor.course_editors, self.course_editor), {self.user}, queries=1)

    def test_course_editors_when_no_editors(self):
        # two queries: one to check for valid editors, one for everybody in group
        self.assertResultsEqual(partial(CourseEditor.course_editors, self.course_bad_editor_in_group),
                                {self.user, self.good_editor}, queries=2)


@ddt.ddt
class CourseRunTests(OAuth2Mixin, TestCase):
    """ Tests for the `CourseRun` model. """

    def setUp(self):
        super(CourseRunTests, self).setUp()
        self.course_run = factories.CourseRunFactory()
        self.partner = self.course_run.course.partner

    def mock_ecommerce_publication(self):
        url = '{root}publication/'.format(root=self.partner.ecommerce_api_url)
        responses.add(responses.POST, url, json={}, status=200)

    def test_enrollable_seats(self):
        """ Verify the expected seats get returned. """
        course_run = factories.CourseRunFactory(start=None, end=None, enrollment_start=None, enrollment_end=None)
        verified_seat = factories.SeatFactory(course_run=course_run, type=Seat.VERIFIED, upgrade_deadline=None)
        professional_seat = factories.SeatFactory(course_run=course_run, type=Seat.PROFESSIONAL, upgrade_deadline=None)
        honor_seat = factories.SeatFactory(course_run=course_run, type=Seat.HONOR, upgrade_deadline=None)
        assert course_run.enrollable_seats([Seat.VERIFIED, Seat.PROFESSIONAL]) == [verified_seat, professional_seat]

        # The method should not care about the course run's start date.
        course_run.start = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        course_run.save()
        assert course_run.enrollable_seats([Seat.VERIFIED, Seat.PROFESSIONAL]) == [verified_seat, professional_seat]

        # Enrollable seats of any type should be returned when no type parameter is specified.
        assert course_run.enrollable_seats() == [verified_seat, professional_seat, honor_seat]

    def test_has_enrollable_seats(self):
        """ Verify the expected value of has_enrollable_seats is returned. """
        course_run = factories.CourseRunFactory(start=None, end=None, enrollment_start=None, enrollment_end=None)
        factories.SeatFactory(course_run=course_run, type=Seat.VERIFIED, upgrade_deadline=None)
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
        """ Verify the slug is created on first save from the title. """
        course_run = CourseRunFactory(title='Test Title')
        self.assertEqual(course_run.slug, 'test-title')

    def test_empty_slug_defined_on_save(self):
        """ Verify the slug is defined on publication if it wasn't set already. """
        toggle_switch('publish_course_runs_to_marketing_site')

        with mock.patch.object(CourseRunMarketingSitePublisher, 'publish_obj', return_value=None):
            self.course_run.slug = ''
            self.course_run.title = 'Test Title'
            self.course_run.save()
            self.assertEqual(self.course_run.slug, 'test-title')

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
            factories.SeatFactory.create(course_run=course_run, type=seat_type, price=price)
        self.assertEqual(course_run.has_enrollable_paid_seats(), expected_result)

    def test_first_enrollable_paid_seat_sku(self):
        """
        Verify that first_enrollable_paid_seat_sku returns sku of first paid seat.
        """
        course_run = factories.CourseRunFactory.create()
        factories.SeatFactory.create(course_run=course_run, type='verified', price=10, sku='ABCDEF')
        self.assertEqual(course_run.first_enrollable_paid_seat_sku(), 'ABCDEF')

    def test_first_enrollable_paid_seat_price(self):
        """
        Verify that first_enrollable_paid_seat_price returns price of first paid seat.
        """
        course_run = factories.CourseRunFactory.create()
        factories.SeatFactory.create(course_run=course_run, type='verified', price=10, sku='ABCDEF')
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
            factories.SeatFactory.create(course_run=course_run, type=seat_type, price=price, upgrade_deadline=deadline)

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
        factories.SeatFactory.create(course_run=course_run, upgrade_deadline=deadline, type='verified', price=1)
        assert course_run.is_current_and_still_upgradeable() == is_current

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

        self.partner.marketing_site_url_root = ''
        self.partner.save()

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

    def test_image_url(self):
        assert self.course_run.image_url == self.course_run.course.image_url

    def test_get_video(self):
        assert self.course_run.get_video == self.course_run.video
        self.course_run.video = None
        self.course_run.save()
        assert self.course_run.get_video == self.course_run.course.video

    def test_official_created(self):
        self.mock_access_token()
        self.mock_ecommerce_publication()

        self.course_run.draft = True
        self.course_run.status = CourseRunStatus.Reviewed
        self.course_run.course.draft = True
        factories.SeatFactory(course_run=self.course_run, draft=True)
        # We have to specify a SeatType that exists in Seat.ENTITLEMENT_MODES in order for the
        # official version of the Entitlement to be created
        entitlement_mode = SeatType.objects.get(slug='verified')
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
        self.course_run.course.canonical_course_run = self.course_run
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
        official_course = factories.CourseFactory.create()
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

    @ddt.data(
        (None, False),
        (datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10), False),
        (datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=10), True),
    )
    @ddt.unpack
    @mock.patch('course_discovery.apps.course_metadata.emails.send_email_for_reviewed')
    def test_reviewed_with_go_live_date(self, when, published, mock_email):
        draft = factories.CourseRunFactory(draft=True, go_live_date=when, announcement=None)

        draft.status = CourseRunStatus.Reviewed
        draft.save()
        draft.refresh_from_db()

        for run in [draft, draft.official_version]:
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
        draft = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, announcement=None, draft=True)
        official = factories.CourseRunFactory(status=CourseRunStatus.Unpublished, announcement=None, draft=False,
                                              course=draft.course, draft_version=draft)

        self.assertTrue(official.publish())
        draft.refresh_from_db()

        self.assertEqual(draft.status, CourseRunStatus.Published)
        self.assertIsNotNone(draft.announcement)
        self.assertEqual(official.status, CourseRunStatus.Published)
        self.assertIsNotNone(official.announcement)

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
    )
    @ddt.unpack
    def test_is_marketable(self, status, create_seats, create_marketing_url, expected):
        course_run = factories.CourseRunFactory.create(status=status)
        if not create_marketing_url:
            course_run.slug = None
        if create_seats:
            factories.SeatFactory.create(course_run=course_run)

        self.assertEqual(course_run.is_marketable, expected)


@ddt.ddt
class OrganizationTests(TestCase):
    """ Tests for the `Organization` model. """

    def setUp(self):
        super(OrganizationTests, self).setUp()
        self.organization = factories.OrganizationFactory()

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
        expected = '{root}/{slug}'.format(root=self.organization.partner.marketing_site_url_root.strip('/'),
                                          slug=self.organization.marketing_url_path)
        self.assertEqual(self.organization.marketing_url, expected)

    def test_marketing_url_without_marketing_url_path(self):
        """ Verify the property returns None if the Organization has no marketing_url_path set. """
        self.organization.marketing_url_path = ''
        self.assertIsNone(self.organization.marketing_url)


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

    def setUp(self):
        super(ProgramTests, self).setUp()
        transcript_languages = LanguageTag.objects.all()[:2]
        self.subjects = factories.SubjectFactory.create_batch(3)
        self.course_runs = factories.CourseRunFactory.create_batch(
            3, transcript_languages=transcript_languages, course__subjects=self.subjects,
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

    def test_search(self):
        """
        Verify that the program endpoint correctly handles basic elasticsearch queries
        """
        title = 'Some random title'
        expected = set(factories.ProgramFactory.create_batch(1, title=title))
        # Create an extra program that should not show up
        factories.ProgramFactory()
        query = 'title:' + title
        self.assertSetEqual(set(Program.search(query)), expected)

    def test_subject_search(self):
        """
        Verify that the program endpoint correctly handles elasticsearch queries on the subject uuid
        """
        subject = factories.SubjectFactory()
        course = factories.CourseFactory(subjects=[subject])
        expected = set(factories.ProgramFactory.create_batch(1, courses=[course]))
        # Create an extra program that should not show up
        factories.ProgramFactory()
        query = str(subject.uuid)
        self.assertSetEqual(set(Program.search(query)), expected)

    def create_program_with_entitlements_and_seats(self):
        verified_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.VERIFIED)
        program_type = factories.ProgramTypeFactory(applicable_seat_types=[verified_seat_type])
        courses = []
        for __ in range(3):
            entitlement = factories.CourseEntitlementFactory(mode=verified_seat_type, expires=None)
            for __ in range(3):
                factories.SeatFactory(
                    course_run=factories.CourseRunFactory(
                        end=None,
                        enrollment_end=None,
                        course=entitlement.course
                    ),
                    type=Seat.VERIFIED, upgrade_deadline=None
                )
            courses.append(entitlement.course)

        program = factories.ProgramFactory(
            courses=courses,
            one_click_purchase_enabled=True,
            type=program_type,
        )
        return program, courses

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
        verified_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.VERIFIED)
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

    def test_one_click_purchase_eligible_with_entitlements(self):
        """ Verify that program is one click purchase eligible when its courses have entitlement products. """
        # Program has one_click_purchase_enabled set to True,
        # all courses have a verified mode entitlement product and multiple course runs.
        program, __ = self.create_program_with_entitlements_and_seats()
        self.assertTrue(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_ineligible_wrong_mode(self):
        """ Verify that program is not one click purchase eligible if course entitlement product has the wrong mode. """
        program, courses = self.create_program_with_entitlements_and_seats()
        honor_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.HONOR)
        honor_mode_entitlement = courses[0].entitlements.first()
        honor_mode_entitlement.mode = honor_seat_type
        honor_mode_entitlement.save()
        self.assertFalse(program.is_program_eligible_for_one_click_purchase)

    def test_one_click_purchase_ineligible_multiple_entitlements(self):
        """
        Verify that program is not one click purchase eligible if course has
        multiple entitlement products with correct modes.
        """
        program, courses = self.create_program_with_entitlements_and_seats()
        credit_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.CREDIT)
        program.type.applicable_seat_types.add(credit_seat_type)
        # We are limiting each course to a single entitlement so this should raise an IntegrityError
        with self.assertRaises(IntegrityError):
            factories.CourseEntitlementFactory(mode=credit_seat_type, expires=None, course=courses[0])

    def test_one_click_purchase_eligible_with_unpublished_runs(self):
        """ Verify that program with unpublished course runs is one click purchase eligible. """

        verified_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.VERIFIED)
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
        yesterday = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        tomorrow = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        verified_seat_type, __ = SeatType.objects.get_or_create(slug=Seat.VERIFIED)
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

    def test_entitlements(self):
        """ Test entitlements returns only applicable course entitlements. """
        courses = factories.CourseFactory.create_batch(3)
        verified_mode = SeatType.objects.get(slug='verified')
        credit_mode = SeatType.objects.get(slug='credit')
        professional_mode = SeatType.objects.get(slug='professional')
        for i, mode in enumerate([verified_mode, credit_mode, professional_mode]):
            factories.CourseEntitlementFactory(course=courses[i], mode=mode)
        applicable_seat_types = SeatType.objects.filter(name__in=['verified', 'professional'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)

        program = factories.ProgramFactory(type=program_type, courses=courses)
        expected = set([c.entitlements.filter(mode__in=applicable_seat_types).first() for c in courses])
        expected.remove(None)
        self.assertEqual(expected, set(program.entitlements))

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

    @ddt.data(True, False)
    def test_price_ranges_with_entitlements(self, create_seats):
        """ Verifies the price_range property of a program with course entitlement products """
        currency = Currency.objects.get(code='USD')
        test_price = 100
        verified_mode = SeatType.objects.get(slug='verified')
        for course_run in self.course_runs:
            factories.CourseEntitlementFactory(
                currency=currency, course=course_run.course, price=test_price, mode=verified_mode
            )
            if create_seats:
                factories.SeatFactory(type='verified', currency=currency, price=test_price, course_run=course_run)
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
        for course_run in single_course_course_runs:
            factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
            factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=10)
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
        self.assertEqual(str(program_type), program_type.name)


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
        assert self.degree.curricula != []
        assert self.curriculum.program_curriculum is not None
        assert self.curriculum.course_curriculum is not None
        assert self.curriculum.marketing_text is not None
        assert self.degree.lead_capture_list_name is not None
        assert self.degree.lead_capture_image is not None
        assert self.degree.campus_image is not None
        assert self.degree.banner_border_color is not None
        assert self.degree.title_background_image is not None
        assert self.degree.micromasters_background_image is not None
