# -*- coding: utf-8 -*-

import datetime
import re
import urllib

import ddt
import mock
import pytest
import pytz
import requests
import responses
from django.test import TestCase

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata import utils
from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException
from course_discovery.apps.course_metadata.models import Course, CourseEditor, CourseRun, Seat, SeatType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, OrganizationFactory, ProgramFactory,
    SeatFactory
)
from course_discovery.apps.course_metadata.tests.mixins import MarketingSiteAPIClientTestMixin
from course_discovery.apps.course_metadata.utils import (
    calculated_seat_upgrade_deadline, create_missing_entitlement, ensure_draft_world, publish_to_course_metadata,
    serialize_entitlement_for_ecommerce_api, serialize_seat_for_ecommerce_api
)
from course_discovery.apps.publisher.tests.factories import CourseRunFactory as PublisherCourseRunFactory


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
    Test the utility function uslugify
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


class PushToEcommerceTests(OAuth2Mixin, TestCase):
    """
    Test the utility function push_to_ecommerce_for_course_run
    """
    def setUp(self):
        super().setUp()

        # Set up an official that we then convert to a draft
        self.course_run = CourseRunFactory()
        CourseEntitlementFactory(course=self.course_run.course, mode=SeatType.objects.get(slug='verified'))
        SeatFactory(course_run=self.course_run, type='verified', sku=None)
        SeatFactory(course_run=self.course_run, type='audit', sku=None)
        self.course_run = ensure_draft_world(self.course_run).official_version

        # Now we're dealing with just official versions again
        self.course = self.course_run.course
        self.partner = self.course.partner
        self.seats = self.course_run.seats.all()
        self.entitlement = self.course.entitlements.first()
        self.api_root = self.partner.ecommerce_api_url

    def mock_publication(self, status=200):
        responses.add(
            responses.POST,
            urllib.parse.urljoin(self.api_root, 'publication/'),
            status=status,
            json={
                'name': self.course_run.title,
                'message': None,
                'products': [
                    {'expires': '2019-12-21T23:59:59Z', 'product_class': 'Seat', 'price': '50.00',
                     'partner_sku': 'XXXXXXXX',
                     'attribute_values': [{'name': 'certificate_type', 'value': 'verified'},
                                          {'name': 'id_verification_required', 'value': True}]},
                    {'expires': None, 'product_class': 'Seat', 'price': '0.00',
                     'partner_sku': 'YYYYYYYY',
                     'attribute_values': [{'name': 'certificate_type', 'value': ''},
                                          {'name': 'id_verification_required', 'value': False}]},
                    {'product_class': 'Course Entitlement', 'price': '50.00',
                     'partner_sku': 'ZZZZZZZZ',
                     'attribute_values': [{'name': 'certificate_type', 'value': 'verified'}]},
                ],
                'uuid': str(self.course.uuid),
                'id': self.course_run.key,
                'verification_deadline': '2019-12-31T00:00:00Z',
            },
        )

    @responses.activate
    def test_push(self):
        """ Happy path """
        self.mock_access_token()
        self.mock_publication()
        self.assertTrue(utils.push_to_ecommerce_for_course_run(self.course_run))
        for s in self.seats:
            s.refresh_from_db()
        self.entitlement.refresh_from_db()
        self.assertEqual({s.sku for s in self.seats}, {'XXXXXXXX', 'YYYYYYYY'})
        self.assertEqual(self.entitlement.sku, 'ZZZZZZZZ')

        # Check draft versions too
        self.assertEqual({s.sku for s in self.course_run.draft_version.seats.all()}, {'XXXXXXXX', 'YYYYYYYY'})
        self.assertEqual(self.course.draft_version.entitlements.first().sku, 'ZZZZZZZZ')

    def test_status_failure(self):
        self.mock_access_token()
        self.mock_publication(status=500)
        with self.assertRaises(requests.HTTPError):
            utils.push_to_ecommerce_for_course_run(self.course_run)

    def test_no_products(self):
        for seat in self.seats:
            seat.delete()
        self.entitlement.delete()
        self.assertFalse(utils.push_to_ecommerce_for_course_run(self.course_run))

    def test_no_ecommerce_url(self):
        self.partner.ecommerce_api_url = None
        self.partner.save()
        self.assertFalse(utils.push_to_ecommerce_for_course_run(self.course_run))


@pytest.mark.django_db
class TestSerializeSeatForEcommerceApi:
    def test_serialize_seat_for_ecommerce_api(self):
        seat = SeatFactory()
        actual = serialize_seat_for_ecommerce_api(seat)
        assert actual['price'] == str(seat.price)
        assert actual['product_class'] == 'Seat'

    def test_serialize_seat_for_ecommerce_api_with_audit_seat(self):
        seat = SeatFactory(type=Seat.AUDIT)
        actual = serialize_seat_for_ecommerce_api(seat)
        expected = {
            'expires': serialize_datetime(calculated_seat_upgrade_deadline(seat)),
            'price': str(seat.price),
            'product_class': 'Seat',
            'attribute_values': [
                {
                    'name': 'certificate_type',
                    'value': '',
                },
                {
                    'name': 'id_verification_required',
                    'value': False,
                }
            ]
        }

        assert actual == expected

    @pytest.mark.parametrize('seat_type', (Seat.VERIFIED, Seat.PROFESSIONAL))
    def test_serialize_seat_for_ecommerce_api_with_id_verification(self, seat_type):
        seat = SeatFactory(type=seat_type)
        actual = serialize_seat_for_ecommerce_api(seat)
        expected_attribute_values = [
            {
                'name': 'certificate_type',
                'value': seat_type,
            },
            {
                'name': 'id_verification_required',
                'value': True,
            }
        ]
        assert actual['attribute_values'] == expected_attribute_values


@pytest.mark.django_db
class TestSerializeEntitlementForEcommerceApi:
    def test_serialize_entitlement_for_ecommerce_api(self):
        entitlement = CourseEntitlementFactory()
        actual = serialize_entitlement_for_ecommerce_api(entitlement)
        expected = {
            'price': str(entitlement.price),
            'product_class': 'Course Entitlement',
            'attribute_values': [
                {
                    'name': 'certificate_type',
                    'value': entitlement.mode.slug,
                },
            ]
        }

        assert actual == expected


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
        course.authoring_organizations.add(org)
        editor = CourseEditorFactory(course=course)

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

        # Check course editors are moved from the official version to the draft version
        self.assertEqual(CourseEditor.objects.count(), 1)
        self.assertEqual(editor.course, ensured_draft_course)

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

        # check slug history not copied over
        self.assertEqual(ensured_draft_course.url_slug_history.count(), 0)
        self.assertEqual(not_draft_course.url_slug_history.count(), 1)

        # Check official and draft versions match up
        self.assertEqual(ensured_draft_course.official_version, not_draft_course)
        self.assertEqual(not_draft_course.draft_version, ensured_draft_course)

        self.assertEqual(draft_entitlement.official_version, not_draft_entitlement)
        self.assertEqual(not_draft_entitlement.draft_version, draft_entitlement)

    def test_ensure_draft_world_creates_course_entitlement_from_seats(self):
        """
        If the official course has no entitlement, an entitlement is created from the seat data from active runs.
        """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory()
        run = CourseRunFactory(course=course, end=future, enrollment_end=None)
        seat = SeatFactory(course_run=run, type=Seat.VERIFIED)
        ensured_draft_course = utils.ensure_draft_world(course)

        draft_entitlement = ensured_draft_course.entitlements.first()
        self.assertEqual(draft_entitlement.price, seat.price)
        self.assertEqual(draft_entitlement.currency, seat.currency)
        self.assertEqual(draft_entitlement.mode.slug, Seat.VERIFIED)

    def test_ensure_draft_world_creates_audit_course_entitlement_as_last_resort(self):
        """
        If the official course has no entitlement and odd seats, a draft audit entitlement should be created.
        """
        course = CourseFactory()
        ensured_draft_course = utils.ensure_draft_world(course)

        draft_entitlement = ensured_draft_course.entitlements.first()
        self.assertEqual(draft_entitlement.price, 0.00)
        self.assertEqual(draft_entitlement.mode.slug, Seat.AUDIT)


@ddt.ddt
class TestCreateMissingEntitlement(TestCase):
    @ddt.data(
        # single verified seat makes entitlement
        ([[{'type': Seat.VERIFIED, 'price': 50, 'currency': 'EUR'}]], (Seat.VERIFIED, 50, 'EUR')),
        # single professional seat makes entitlement too
        ([[{'type': Seat.PROFESSIONAL, 'price': 70, 'currency': 'USD'}]], (Seat.PROFESSIONAL, 70, 'USD')),
        ([[{'type': Seat.VERIFIED}, {'type': Seat.PROFESSIONAL}]], None),  # multiple valid seats makes nothing
        ([[{'type': Seat.AUDIT}]], None),  # no valid seats make nothing
        ([[]], None),  # no seats at all make nothing
        ([], None),  # no runs at all make nothing
        # runs that disagree about valid seats make nothing
        ([[{'type': Seat.VERIFIED}], [{'type': Seat.PROFESSIONAL}]], None),
        # runs that disagree about price make nothing
        ([[{'type': Seat.VERIFIED, 'price': 10}], [{'type': Seat.VERIFIED, 'price': 20}]], None),
        # runs that disagree about currency make nothing
        ([[{'type': Seat.VERIFIED, 'price': 10, 'currency': 'EUR'}],
          [{'type': Seat.VERIFIED, 'price': 10, 'currency': 'USD'}]], None),
        # multiple agreeing runs makes entitlement
        ([[{'type': Seat.VERIFIED, 'price': 20, 'currency': 'EUR'}],
          [{'type': Seat.VERIFIED, 'price': 20, 'currency': 'EUR'}]], (Seat.VERIFIED, 20, 'EUR')),
        ([[{'type': Seat.MASTERS}, {'type': Seat.CREDIT}, {'type': Seat.PROFESSIONAL, 'price': 10, 'currency': 'USD'}]],
         (Seat.PROFESSIONAL, 10, 'USD')),  # non-relevant seats don't stop us from making an entitlement
    )
    @ddt.unpack
    def test_seat_combos(self, runs, expected):
        """ Verify that the right entitlement gets created when possible """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory()
        for seats in runs:
            run = CourseRunFactory(course=course, end=future, enrollment_end=None)
            for seat in seats:
                if 'currency' in seat:
                    seat['currency'] = Currency.objects.get(code=seat['currency'])
                SeatFactory(**seat, course_run=run)

        self.assertFalse(course.entitlements.exists())  # sanity check
        create_missing_entitlement(course)

        self.assertEqual(course.entitlements.count(), 1 if expected else 0)
        if expected:
            entitlement = course.entitlements.first()
            self.assertEqual(entitlement.mode.slug, expected[0])
            self.assertEqual(entitlement.price, expected[1])
            self.assertEqual(entitlement.currency.code, expected[2])
            self.assertEqual(entitlement.partner, course.partner)
            self.assertFalse(entitlement.draft)  # tested below

    def test_draft_course(self):
        """ Verifies that a draft course will create a draft entitlement """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory(draft=True)
        run = CourseRunFactory(course=course, end=future, enrollment_end=None, draft=True)
        seat = SeatFactory(course_run=run, type=Seat.VERIFIED, draft=True)

        self.assertFalse(course.entitlements.exists())  # sanity check
        create_missing_entitlement(course)

        self.assertEqual(course.entitlements.count(), 1)
        entitlement = course.entitlements.first()
        self.assertEqual(entitlement.mode.slug, Seat.VERIFIED)
        self.assertEqual(entitlement.price, seat.price)
        self.assertEqual(entitlement.currency, seat.currency)
        self.assertTrue(entitlement.draft)

    @ddt.data(
        ((10, -10), 10),
        ((10, 10), 10),
        ((10,), 10),
        ((-10,), -10),
        ((-10, -20), -20),
    )
    @ddt.unpack
    def test_active_runs(self, dates, expected):
        """ Verifies that we only consider active runs (or last inactive) """

        def date_to_price(offset):
            # Because we are just working with date offsets here, to avoid negative prices if we ever require that,
            # we convert a dates to a positive price number
            if offset < 0:
                return offset * -10 + 1
            else:
                return offset * 10

        course = CourseFactory()
        now = datetime.datetime.now(pytz.UTC)
        usd = Currency.objects.get(code='USD')
        for date in dates:
            run = CourseRunFactory(course=course, end=now + datetime.timedelta(days=date), enrollment_end=None)
            SeatFactory(course_run=run, type=Seat.VERIFIED, price=date_to_price(date), currency=usd)

        self.assertFalse(course.entitlements.exists())  # sanity check
        self.assertTrue(create_missing_entitlement(course))

        entitlement = course.entitlements.first()
        self.assertEqual(entitlement.price, date_to_price(expected))

    @mock.patch('course_discovery.apps.course_metadata.utils.push_to_ecommerce_for_course_run')
    def test_push_to_ecommerce(self, mock_push):
        """ Verifies that we push new entitlement to ecommerce """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory()
        run = CourseRunFactory(course=course, end=future, enrollment_end=None)
        SeatFactory(course_run=run, type=Seat.VERIFIED)

        course.canonical_course_run = run
        course.save()

        self.assertFalse(course.entitlements.exists())  # sanity check
        self.assertTrue(create_missing_entitlement(course))

        self.assertEqual(mock_push.call_count, 1)
        self.assertEqual(mock_push.call_args[0][0], run)


# This is also tested through Publisher's api/v1/tests/test_views.py
class TestPublishToCourseMetadata(TestCase):
    def test_no_draft_row(self):
        """ Test that re-publishing when there's already an official row but no draft row yet works fine. """
        cm_run = CourseRunFactory()
        pub_run = PublisherCourseRunFactory(lms_course_id=cm_run.key)
        publish_to_course_metadata(cm_run.course.partner, pub_run)

        cm_run.refresh_from_db()
        cm_run_draft = CourseRun.everything.get(key=cm_run.key, draft=True)

        self.assertEqual(cm_run.draft_version, cm_run_draft)
        self.assertEqual(cm_run.uuid, cm_run_draft.uuid)

    def test_unlinked_draft_row(self):
        """
        Test that re-publishing when there's already a draft row but not linked to the official row.

        Specifically, they have a different UUID and are not linked via draft_version.
        This might happen from historical bugs in the migrate script / old publisher / studio loader.
        """
        cm_run = CourseRunFactory()
        cm_run_draft = ensure_draft_world(cm_run)
        cm_run.draft_version = None
        cm_run.save()
        cm_run_draft.uuid = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        cm_run_draft.save()
        pub_run = PublisherCourseRunFactory(lms_course_id=cm_run.key)
        publish_to_course_metadata(cm_run.course.partner, pub_run)

        cm_run.refresh_from_db()
        cm_run_draft.refresh_from_db()

        self.assertEqual(cm_run.draft_version, cm_run_draft)
        self.assertEqual(cm_run.uuid, cm_run_draft.uuid)
        self.assertNotEqual(cm_run_draft.uuid, 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
