# -*- coding: utf-8 -*-

import re

import ddt
import responses
from django.test import TestCase

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.course_metadata import utils
from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEntitlementFactory, CourseFactory, CourseRunFactory, OrganizationFactory, ProgramFactory, SeatFactory
)
from course_discovery.apps.course_metadata.tests.mixins import MarketingSiteAPIClientTestMixin


@ddt.ddt
class UploadToFieldNamePathTests(TestCase):
    """
    Test the utiltity object 'UploadtoFieldNamePath'
    """
    def setUp(self):
        super(UploadToFieldNamePathTests, self).setUp()
        self.program = ProgramFactory()

    @ddt.data(
        ('/media/program/', 'uuid', '.jpeg'),
        ('/media/program/', 'title', '.jpeg'),
        ('/media/', 'uuid', '.jpeg'),
        ('/media/', 'title', '.txt'),
        ('', 'title', ''),
    )
    @ddt.unpack
    def test_upload_to(self, path, field, ext):
        upload_to = utils.UploadToFieldNamePath(populate_from=field, path=path)
        upload_path = upload_to(self.program, 'name' + ext)
        regex = re.compile(path + str(getattr(self.program, field)) + '-[a-f0-9]{12}' + ext)
        self.assertTrue(regex.match(upload_path))


@ddt.ddt
class UslugifyTests(TestCase):
    """
    Test the utiltity function uslugify
    """
    @ddt.data(
        ('技研究', 'ji-yan-jiu'),
        ('عائشة', 'ysh'),
        ('TWO WORDS', 'two-words'),
    )
    @ddt.unpack
    def test_uslugify(self, string, expected):
        output = utils.uslugify(string)
        self.assertEqual(output, expected)


class MarketingSiteAPIClientTests(MarketingSiteAPIClientTestMixin):
    """
    Unit test cases for MarketinSiteAPIClient
    """
    def setUp(self):
        super(MarketingSiteAPIClientTests, self).setUp()
        self.api_client = utils.MarketingSiteAPIClient(
            self.username,
            self.password,
            self.api_root
        )

    @responses.activate
    def test_init_session(self):
        self.mock_login_response(200)
        session = self.api_client.init_session
        self.assert_responses_call_count(2)
        self.assertIsNotNone(session)

    @responses.activate
    def test_init_session_failed(self):
        self.mock_login_response(500)
        with self.assertRaises(MarketingSiteAPIClientException):
            self.api_client.init_session  # pylint: disable=pointless-statement

    @responses.activate
    def test_csrf_token(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        csrf_token = self.api_client.csrf_token
        self.assert_responses_call_count(3)
        self.assertEqual(self.csrf_token, csrf_token)

    @responses.activate
    def test_csrf_token_failed(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(500)
        with self.assertRaises(MarketingSiteAPIClientException):
            self.api_client.csrf_token  # pylint: disable=pointless-statement

    @responses.activate
    def test_user_id(self):
        self.mock_login_response(200)
        self.mock_user_id_response(200)
        user_id = self.api_client.user_id
        self.assert_responses_call_count(3)
        self.assertEqual(self.user_id, user_id)

    @responses.activate
    def test_user_id_failed(self):
        self.mock_login_response(200)
        self.mock_user_id_response(500)
        with self.assertRaises(MarketingSiteAPIClientException):
            self.api_client.user_id  # pylint: disable=pointless-statement

    @responses.activate
    def test_api_session(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        api_session = self.api_client.api_session
        self.assert_responses_call_count(3)
        self.assertIsNotNone(api_session)
        self.assertEqual(api_session.headers.get('Content-Type'), 'application/json')
        self.assertEqual(api_session.headers.get('X-CSRF-Token'), self.csrf_token)

    @responses.activate
    def test_api_session_failed(self):
        self.mock_login_response(500)
        self.mock_csrf_token_response(500)
        with self.assertRaises(MarketingSiteAPIClientException):
            self.api_client.api_session  # pylint: disable=pointless-statement


@ddt.ddt
class TestEnsureDraftWorld(SiteMixin, TestCase):
    def setUp(self):
        super().setUp()

    @ddt.data(
        None,
        {'weeks_to_complete': 7},
        {'weeks_to_complete': 7, 'title_override': 'New Title'},
    )
    def test_set_draft_state(self, attrs):
        course_run = CourseRunFactory()
        draft_course_run, original_course_run = utils.set_draft_state(course_run, CourseRun, attrs)

        self.assertEqual(1, len(CourseRun.objects.all()))
        self.assertEqual(2, len(CourseRun.everything.all()))

        self.assertTrue(draft_course_run.draft)
        self.assertFalse(original_course_run.draft)

        if attrs:
            model_fields = [field.name for field in CourseRun._meta.get_fields()]
            diff_of_fields = [field for field in filter(
                lambda f: getattr(original_course_run, f, None) != getattr(draft_course_run, f, None),
                model_fields
            )]
            for key, value in attrs.items():
                # Make sure that any attributes we changed are different in the draft course run from the original
                self.assertIn(key, diff_of_fields)
                self.assertEqual(getattr(draft_course_run, key), value)

    def test_set_draft_state_with_foreign_key(self):
        course = CourseFactory()
        course_run = CourseRunFactory(course=course)
        draft_course, original_course = utils.set_draft_state(course, Course)
        draft_course_run, original_course_run = utils.set_draft_state(course_run, CourseRun, {'course': draft_course})

        self.assertEqual(1, len(CourseRun.objects.all()))
        self.assertEqual(2, len(CourseRun.everything.all()))
        self.assertEqual(1, len(Course.objects.all()))
        self.assertEqual(2, len(Course.everything.all()))

        self.assertTrue(draft_course_run.draft)
        self.assertFalse(original_course_run.draft)

        self.assertTrue(draft_course.draft)
        self.assertFalse(original_course.draft)

        self.assertNotEqual(draft_course_run.course, original_course_run.course)
        self.assertEqual(draft_course_run.course, draft_course)
        self.assertEqual(original_course_run.course, original_course)

    def test_ensure_draft_world_draft_obj_given(self):
        course_run = CourseRunFactory(draft=True)
        ensured_draft_course_run = utils.ensure_draft_world(course_run)

        self.assertEqual(ensured_draft_course_run, course_run)
        self.assertEqual(ensured_draft_course_run.id, course_run.id)
        self.assertEqual(ensured_draft_course_run.uuid, course_run.uuid)
        self.assertEqual(ensured_draft_course_run.draft, course_run.draft)

    def test_ensure_draft_world_not_draft_course_run_given(self):
        course = CourseFactory()
        course_run = CourseRunFactory(course=course)
        verified_seat = SeatFactory(type='verified', course_run=course_run)
        audit_seat = SeatFactory(type='audit', course_run=course_run)
        course_run.seats.add(verified_seat, audit_seat)

        ensured_draft_course_run = utils.ensure_draft_world(course_run)
        not_draft_course_run = CourseRun.objects.get(uuid=course_run.uuid)

        self.assertNotEqual(ensured_draft_course_run, not_draft_course_run)
        self.assertEqual(ensured_draft_course_run.uuid, not_draft_course_run.uuid)
        self.assertTrue(ensured_draft_course_run.draft)
        self.assertNotEqual(ensured_draft_course_run.course, not_draft_course_run.course)
        self.assertEqual(ensured_draft_course_run.course.uuid, not_draft_course_run.course.uuid)

        # Check slugs are equal
        self.assertEqual(ensured_draft_course_run.slug, not_draft_course_run.slug)

        # Seat checks
        draft_seats = ensured_draft_course_run.seats.all()
        not_draft_seats = not_draft_course_run.seats.all()
        self.assertNotEqual(draft_seats, not_draft_seats)
        self.assertEqual(len(draft_seats), len(not_draft_seats))
        for i, __ in enumerate(draft_seats):
            self.assertEqual(draft_seats[i].price, not_draft_seats[i].price)
            self.assertEqual(draft_seats[i].sku, not_draft_seats[i].sku)
            self.assertNotEqual(draft_seats[i].course_run, not_draft_seats[i].course_run)
            self.assertEqual(draft_seats[i].course_run.uuid, not_draft_seats[i].course_run.uuid)
            self.assertEqual(draft_seats[i].official_version, not_draft_seats[i])
            self.assertEqual(not_draft_seats[i].draft_version, draft_seats[i])

        # Check draft course is also created
        draft_course = ensured_draft_course_run.course
        not_draft_course = Course.objects.get(uuid=course.uuid)
        self.assertNotEqual(draft_course, not_draft_course)
        self.assertEqual(draft_course.uuid, not_draft_course.uuid)
        self.assertTrue(draft_course.draft)

        # Check official and draft versions match up
        self.assertEqual(ensured_draft_course_run.official_version, not_draft_course_run)
        self.assertEqual(not_draft_course_run.draft_version, ensured_draft_course_run)

    def test_ensure_draft_world_not_draft_course_given(self):
        course = CourseFactory()
        entitlement = CourseEntitlementFactory(course=course)
        course.entitlements.add(entitlement)
        course_runs = CourseRunFactory.create_batch(3, course=course)
        for run in course_runs:
            course.course_runs.add(run)
        course.canonical_course_run = course_runs[0]
        course.save()
        org = OrganizationFactory()
        course.authoring_organizations.add(org)  # pylint: disable=no-member

        ensured_draft_course = utils.ensure_draft_world(course)
        not_draft_course = Course.objects.get(uuid=course.uuid)

        self.assertNotEqual(ensured_draft_course, not_draft_course)
        self.assertEqual(ensured_draft_course.uuid, not_draft_course.uuid)
        self.assertTrue(ensured_draft_course.draft)

        # Check slugs are equal
        self.assertEqual(ensured_draft_course.slug, not_draft_course.slug)

        # Check authoring orgs are equal
        self.assertEqual(list(ensured_draft_course.authoring_organizations.all()),
                         list(not_draft_course.authoring_organizations.all()))

        # Check canonical course run was updated
        self.assertNotEqual(ensured_draft_course.canonical_course_run, not_draft_course.canonical_course_run)
        self.assertTrue(ensured_draft_course.canonical_course_run.draft)
        self.assertEqual(ensured_draft_course.canonical_course_run.uuid, not_draft_course.canonical_course_run.uuid)

        # Check course runs all share the same UUIDs, but are now all drafts
        not_draft_course_runs_uuids = [run.uuid for run in course_runs]
        draft_course_runs_uuids = [
            run.uuid for run in ensured_draft_course.course_runs.all()
        ]
        self.assertListEqual(draft_course_runs_uuids, not_draft_course_runs_uuids)

        # Entitlement checks
        draft_entitlement = ensured_draft_course.entitlements.first()
        not_draft_entitlement = not_draft_course.entitlements.first()
        self.assertNotEqual(draft_entitlement, not_draft_entitlement)
        self.assertEqual(draft_entitlement.price, not_draft_entitlement.price)
        self.assertEqual(draft_entitlement.sku, not_draft_entitlement.sku)
        self.assertNotEqual(draft_entitlement.course, not_draft_entitlement.course)
        self.assertEqual(draft_entitlement.course.uuid, not_draft_entitlement.course.uuid)

        # Check official and draft versions match up
        self.assertEqual(ensured_draft_course.official_version, not_draft_course)
        self.assertEqual(not_draft_course.draft_version, ensured_draft_course)

        self.assertEqual(draft_entitlement.official_version, not_draft_entitlement)
        self.assertEqual(not_draft_entitlement.draft_version, draft_entitlement)

    def test_ensure_draft_world_no_course_entitlement(self):
        ''' If the official course has no entitlement, a draft audit entitlement should be created. '''
        course = CourseFactory()
        ensured_draft_course = utils.ensure_draft_world(course)

        draft_entitlement = ensured_draft_course.entitlements.first()
        self.assertEqual(draft_entitlement.price, 0.00)
        self.assertEqual(draft_entitlement.mode.slug, 'audit')
