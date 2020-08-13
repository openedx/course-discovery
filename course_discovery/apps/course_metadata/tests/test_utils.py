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
from course_discovery.apps.course_metadata.exceptions import (
    EcommerceSiteAPIClientException, MarketingSiteAPIClientException
)
from course_discovery.apps.course_metadata.models import Course, CourseEditor, CourseRun, Seat, SeatType, Track
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, ModeFactory, OrganizationFactory,
    ProgramFactory, SeatFactory, SeatTypeFactory
)
from course_discovery.apps.course_metadata.tests.mixins import MarketingSiteAPIClientTestMixin
from course_discovery.apps.course_metadata.utils import (
    calculated_seat_upgrade_deadline, clean_html, create_missing_entitlement, ensure_draft_world,
    serialize_entitlement_for_ecommerce_api, serialize_seat_for_ecommerce_api
)


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
        audit_track = Track.objects.get(seat_type__slug=Seat.AUDIT)
        verified_track = Track.objects.get(seat_type__slug=Seat.VERIFIED)
        self.course_run = CourseRunFactory(type__tracks=[audit_track, verified_track])
        CourseEntitlementFactory(course=self.course_run.course, mode=SeatTypeFactory.verified())
        SeatFactory(course_run=self.course_run, type=SeatTypeFactory.verified(), sku=None)
        SeatFactory(course_run=self.course_run, type=SeatTypeFactory.audit(), sku=None)
        self.course_run = ensure_draft_world(self.course_run).official_version

        # Now we're dealing with just official versions again
        self.course = self.course_run.course
        self.partner = self.course.partner
        self.seats = self.course_run.seats.all()
        self.entitlement = self.course.entitlements.first()
        self.api_root = self.partner.ecommerce_api_url

    def mock_publication(self, status=200, json=None):
        responses.add(
            responses.POST,
            urllib.parse.urljoin(self.api_root, 'publication/'),
            status=status,
            json=json if json else {
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
        self.partner.lms_url = 'http://127.0.0.1:8000'
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
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.mock_access_token()
        self.mock_publication(status=500)
        with self.assertRaises(requests.HTTPError):
            utils.push_to_ecommerce_for_course_run(self.course_run)

        responses.reset()
        self.mock_publication(status=500, json={'error': 'Test error message'})
        with self.assertRaises(EcommerceSiteAPIClientException):
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


@ddt.ddt
class TestSerializeSeatForEcommerceApi(TestCase):
    @ddt.data(
        ('', False),
        ('verified', True),
    )
    @ddt.unpack
    def test_serialize_seat_for_ecommerce_api(self, certificate_type, is_id_verified):
        seat = SeatFactory()
        mode = ModeFactory(certificate_type=certificate_type, is_id_verified=is_id_verified)
        actual = serialize_seat_for_ecommerce_api(seat, mode)
        expected = {
            'expires': serialize_datetime(calculated_seat_upgrade_deadline(seat)),
            'price': str(seat.price),
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': seat.sku}],
            'attribute_values': [
                {
                    'name': 'certificate_type',
                    'value': mode.certificate_type,
                },
                {
                    'name': 'id_verification_required',
                    'value': mode.is_id_verified,
                }
            ]
        }
        self.assertEqual(actual, expected)
        seat.sku = None
        actual = serialize_seat_for_ecommerce_api(seat, mode)
        expected['stockrecords'][0]['partner_sku'] = None
        self.assertEqual(actual, expected)


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
            diff_of_fields = list(filter(
                lambda f: getattr(original_course_run, f, None) != getattr(draft_course_run, f, None),
                model_fields
            ))
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
        verified_seat = SeatFactory(type=SeatTypeFactory.verified(), course_run=course_run)
        audit_seat = SeatFactory(type=SeatTypeFactory.audit(), course_run=course_run)
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
        seat = SeatFactory(course_run=run, type=SeatTypeFactory.verified())
        ensured_draft_course = utils.ensure_draft_world(course)

        draft_entitlement = ensured_draft_course.entitlements.first()
        self.assertEqual(draft_entitlement.price, seat.price)
        self.assertEqual(draft_entitlement.currency, seat.currency)
        self.assertEqual(draft_entitlement.mode.slug, Seat.VERIFIED)


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
                if 'type' in seat:
                    seat['type'] = SeatType.objects.get_or_create(slug=seat['type'])[0]
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
        seat = SeatFactory(course_run=run, type=SeatTypeFactory.verified(), draft=True)

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
            SeatFactory(course_run=run, type=SeatTypeFactory.verified(), price=date_to_price(date), currency=usd)

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
        SeatFactory(course_run=run, type=SeatTypeFactory.verified())

        course.canonical_course_run = run
        course.save()

        self.assertFalse(course.entitlements.exists())  # sanity check
        self.assertTrue(create_missing_entitlement(course))

        self.assertEqual(mock_push.call_count, 1)
        self.assertEqual(mock_push.call_args[0][0], run)


# pylint: disable=line-too-long
@ddt.ddt
class CleanHtmlTests(TestCase):
    @ddt.data(
        # Make sure we leave certain things alone
        ('', '',),
        ('<p>Para</p>', '<p>Para</p>'),
        ('<p>One</p><p>Two</p>', '<p>One</p>\n<p>Two</p>'),
        ('<em>Em</em>', '<p><em>Em</em></p>'),
        ('Entities&amp;', '<p>Entities&amp;</p>'),
        ('<a href="https://example.com/">Link</a>', '<p><a href="https://example.com/">Link</a></p>'),
        ('<ul><li>1</li><li>2</li></ul>', '<ul>\n<li>1</li>\n<li>2</li>\n</ul>'),

        # Make sure our diacritics are handled nicely
        # pylint: disable=line-too-long
        ('These are our at risk characters áàãäéêèíîóôœòöúùü', '<p>These are our at risk characters áàãäéêèíîóôœòöúùü</p>'),
        # pylint: disable=line-too-long
        ('These are our at risk characters &#xE1;&#xE0;&#xE3;&#xE4;&#xE9;&#xEA;&#xE8;&#xED;&#xEE;&#xF3;&#xF4;&#x153;&#xF2;&#xF6;&#xFA;&#xF9;&#xFC;', '<p>These are our at risk characters áàãäéêèíîóôœòöúùü</p>'),

        # Make sure we treat incoming text as HTML, not markdown
        ('Bare Text\nSame Para\n\nNew Para', '<p>Bare Text Same Para New Para</p>'),

        # And make sure we strip what we should
        ('<p class="float">Class</p>', '<p>Class</p>'),
        ('<p style="float">Inline Style</p>', '<p>Inline Style</p>'),
        ('<style>Style</style>', ''),
        ('<script>Script</script>', ''),
        ('NB&nbsp;SP', '<p>NBSP</p>'),

        # Make sure that only spans with lang tags are preserved in the saved string
        ('<p><span lang="en">with lang</span></p>', '<p><span lang="en">with lang</span></p>'),
        ('<p><span class="body" lang="en">lang and class</span></p>', '<p><span lang="en">lang and class</span></p>'),
        ('<p><span class="body">class only</span></p>', '<p>class only</p>'),

        # A sample text from real life when pasting from Microsoft Word into a rich text editor
        ('<p>qwerty</p><p>&nbsp;</p><p><!-- [if !mso]><style>v\\:* {behavior:url(#default#VML);}o\\:* {behavior:url(#default#VML);}w\\:* {behavior:url(#default#VML);}.shape {behavior:url(#default#VML);}</style><![endif]--><!-- [if gte mso 9]><xml> <o:OfficeDocumentSettings>  <o:AllowPNG/> </o:OfficeDocumentSettings></xml><![endif]--> <!-- [if gte mso 9]><xml> <w:WordDocument>  <w:View>Normal</w:View>  <w:Zoom>0</w:Zoom>  <w:TrackMoves>false</w:TrackMoves>  <w:TrackFormatting/>  <w:PunctuationKerning/>  <w:ValidateAgainstSchemas/>  <w:SaveIfXMLInvalid>false</w:SaveIfXMLInvalid>  <w:IgnoreMixedContent>false</w:IgnoreMixedContent>  <w:AlwaysShowPlaceholderText>false</w:AlwaysShowPlaceholderText>  <w:DoNotPromoteQF/>  <w:LidThemeOther>EN-US</w:LidThemeOther>  <w:LidThemeAsian>X-NONE</w:LidThemeAsian>  <w:LidThemeComplexScript>X-NONE</w:LidThemeComplexScript>  <w:Compatibility>   <w:BreakWrappedTables/>   <w:SnapToGridInCell/>   <w:WrapTextWithPunct/>   <w:UseAsianBreakRules/>   <w:DontGrowAutofit/>   <w:SplitPgBreakAndParaMark/>   <w:EnableOpenTypeKerning/>   <w:DontFlipMirrorIndents/>   <w:OverrideTableStyleHps/>  </w:Compatibility>  <m:mathPr>   <m:mathFont m:val="Cambria Math"/>   <m:brkBin m:val="before"/>   <m:brkBinSub m:val="&#45;-"/>   <m:smallFrac m:val="off"/>   <m:dispDef/>   <m:lMargin m:val="0"/>   <m:rMargin m:val="0"/>   <m:defJc m:val="centerGroup"/>   <m:wrapIndent m:val="1440"/>   <m:intLim m:val="subSup"/>   <m:naryLim m:val="undOvr"/>  </m:mathPr></w:WordDocument></xml><![endif]--><!-- [if gte mso 9]><xml> <w:LatentStyles DefLockedState="false" DefUnhideWhenUsed="false"  DefSemiHidden="false" DefQFormat="false" DefPriority="99"  LatentStyleCount="375">  <w:LsdException Locked="false" Priority="0" QFormat="true" Name="Normal"/>  <w:LsdException Locked="false" Priority="9" QFormat="true" Name="heading 1"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 2"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 3"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 4"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 5"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 6"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 7"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 8"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="heading 9"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 6"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 7"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 8"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index 9"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 1"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 2"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 3"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 4"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 5"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 6"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 7"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 8"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" Name="toc 9"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Normal Indent"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="footnote text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="annotation text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="header"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   QFormat="true" Name="footer"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="index heading"/>  <w:LsdException Locked="false" Priority="35" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="caption"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="table of figures"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="envelope address"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="envelope return"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="footnote reference"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="annotation reference"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="line number"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="page number"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="endnote reference"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="endnote text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="table of authorities"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="macro"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="toa heading"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List"/>  <w:LsdException Locked="false" Priority="9" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="List Bullet"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Number"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Bullet 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Bullet 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Bullet 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Bullet 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Number 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Number 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Number 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Number 5"/>  <w:LsdException Locked="false" Priority="10" QFormat="true" Name="Title"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Closing"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Signature"/>  <w:LsdException Locked="false" Priority="1" SemiHidden="true"   UnhideWhenUsed="true" Name="Default Paragraph Font"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text Indent"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Continue"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Continue 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Continue 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Continue 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="List Continue 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Message Header"/>  <w:LsdException Locked="false" Priority="11" QFormat="true" Name="Subtitle"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Salutation"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Date"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text First Indent"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text First Indent 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Note Heading"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text Indent 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Body Text Indent 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Block Text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Hyperlink"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="FollowedHyperlink"/>  <w:LsdException Locked="false" Priority="22" QFormat="true" Name="Strong"/>  <w:LsdException Locked="false" Priority="20" QFormat="true" Name="Emphasis"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Document Map"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Plain Text"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="E-mail Signature"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Top of Form"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Bottom of Form"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Normal (Web)"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Acronym"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Address"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Cite"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Code"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Definition"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Keyboard"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Preformatted"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Sample"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Typewriter"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="HTML Variable"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Normal Table"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="annotation subject"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="No List"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Outline List 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Outline List 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Outline List 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Simple 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Simple 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Simple 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Classic 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Classic 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Classic 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Classic 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Colorful 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Colorful 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Colorful 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Columns 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Columns 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Columns 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Columns 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Columns 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 6"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 7"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Grid 8"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 4"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 5"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 6"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 7"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table List 8"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table 3D effects 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table 3D effects 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table 3D effects 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Contemporary"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Elegant"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Professional"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Subtle 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Subtle 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Web 1"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Web 2"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Web 3"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Balloon Text"/>  <w:LsdException Locked="false" Priority="39" Name="Table Grid"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Table Theme"/>  <w:LsdException Locked="false" SemiHidden="true" Name="Placeholder Text"/>  <w:LsdException Locked="false" Priority="1" QFormat="true" Name="No Spacing"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading"/>  <w:LsdException Locked="false" Priority="61" Name="Light List"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 1"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 1"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 1"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 1"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 1"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 1"/>  <w:LsdException Locked="false" SemiHidden="true" Name="Revision"/>  <w:LsdException Locked="false" Priority="34" QFormat="true"   Name="List Paragraph"/>  <w:LsdException Locked="false" Priority="29" QFormat="true" Name="Quote"/>  <w:LsdException Locked="false" Priority="30" QFormat="true"   Name="Intense Quote"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 1"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 1"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 1"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 1"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 1"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 1"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 1"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 1"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 2"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 2"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 2"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 2"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 2"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 2"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 2"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 2"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 2"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 2"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 2"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 2"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 2"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 2"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 3"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 3"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 3"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 3"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 3"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 3"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 3"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 3"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 3"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 3"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 3"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 3"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 3"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 3"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 4"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 4"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 4"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 4"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 4"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 4"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 4"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 4"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 4"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 4"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 4"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 4"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 4"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 4"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 5"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 5"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 5"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 5"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 5"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 5"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 5"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 5"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 5"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 5"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 5"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 5"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 5"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 5"/>  <w:LsdException Locked="false" Priority="60" Name="Light Shading Accent 6"/>  <w:LsdException Locked="false" Priority="61" Name="Light List Accent 6"/>  <w:LsdException Locked="false" Priority="62" Name="Light Grid Accent 6"/>  <w:LsdException Locked="false" Priority="63" Name="Medium Shading 1 Accent 6"/>  <w:LsdException Locked="false" Priority="64" Name="Medium Shading 2 Accent 6"/>  <w:LsdException Locked="false" Priority="65" Name="Medium List 1 Accent 6"/>  <w:LsdException Locked="false" Priority="66" Name="Medium List 2 Accent 6"/>  <w:LsdException Locked="false" Priority="67" Name="Medium Grid 1 Accent 6"/>  <w:LsdException Locked="false" Priority="68" Name="Medium Grid 2 Accent 6"/>  <w:LsdException Locked="false" Priority="69" Name="Medium Grid 3 Accent 6"/>  <w:LsdException Locked="false" Priority="70" Name="Dark List Accent 6"/>  <w:LsdException Locked="false" Priority="71" Name="Colorful Shading Accent 6"/>  <w:LsdException Locked="false" Priority="72" Name="Colorful List Accent 6"/>  <w:LsdException Locked="false" Priority="73" Name="Colorful Grid Accent 6"/>  <w:LsdException Locked="false" Priority="19" QFormat="true"   Name="Subtle Emphasis"/>  <w:LsdException Locked="false" Priority="21" QFormat="true"   Name="Intense Emphasis"/>  <w:LsdException Locked="false" Priority="31" QFormat="true"   Name="Subtle Reference"/>  <w:LsdException Locked="false" Priority="32" QFormat="true"   Name="Intense Reference"/>  <w:LsdException Locked="false" Priority="33" QFormat="true" Name="Book Title"/>  <w:LsdException Locked="false" Priority="37" SemiHidden="true"   UnhideWhenUsed="true" Name="Bibliography"/>  <w:LsdException Locked="false" Priority="39" SemiHidden="true"   UnhideWhenUsed="true" QFormat="true" Name="TOC Heading"/>  <w:LsdException Locked="false" Priority="41" Name="Plain Table 1"/>  <w:LsdException Locked="false" Priority="42" Name="Plain Table 2"/>  <w:LsdException Locked="false" Priority="43" Name="Plain Table 3"/>  <w:LsdException Locked="false" Priority="44" Name="Plain Table 4"/>  <w:LsdException Locked="false" Priority="45" Name="Plain Table 5"/>  <w:LsdException Locked="false" Priority="40" Name="Grid Table Light"/>  <w:LsdException Locked="false" Priority="46" Name="Grid Table 1 Light"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark"/>  <w:LsdException Locked="false" Priority="51" Name="Grid Table 6 Colorful"/>  <w:LsdException Locked="false" Priority="52" Name="Grid Table 7 Colorful"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 1"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 1"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 1"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 1"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 1"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 1"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 1"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 2"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 2"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 2"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 2"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 2"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 2"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 2"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 3"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 3"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 3"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 3"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 3"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 3"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 3"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 4"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 4"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 4"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 4"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 4"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 4"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 4"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 5"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 5"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 5"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 5"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 5"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 5"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 5"/>  <w:LsdException Locked="false" Priority="46"   Name="Grid Table 1 Light Accent 6"/>  <w:LsdException Locked="false" Priority="47" Name="Grid Table 2 Accent 6"/>  <w:LsdException Locked="false" Priority="48" Name="Grid Table 3 Accent 6"/>  <w:LsdException Locked="false" Priority="49" Name="Grid Table 4 Accent 6"/>  <w:LsdException Locked="false" Priority="50" Name="Grid Table 5 Dark Accent 6"/>  <w:LsdException Locked="false" Priority="51"   Name="Grid Table 6 Colorful Accent 6"/>  <w:LsdException Locked="false" Priority="52"   Name="Grid Table 7 Colorful Accent 6"/>  <w:LsdException Locked="false" Priority="46" Name="List Table 1 Light"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark"/>  <w:LsdException Locked="false" Priority="51" Name="List Table 6 Colorful"/>  <w:LsdException Locked="false" Priority="52" Name="List Table 7 Colorful"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 1"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 1"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 1"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 1"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 1"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 1"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 1"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 2"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 2"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 2"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 2"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 2"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 2"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 2"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 3"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 3"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 3"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 3"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 3"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 3"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 3"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 4"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 4"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 4"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 4"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 4"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 4"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 4"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 5"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 5"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 5"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 5"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 5"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 5"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 5"/>  <w:LsdException Locked="false" Priority="46"   Name="List Table 1 Light Accent 6"/>  <w:LsdException Locked="false" Priority="47" Name="List Table 2 Accent 6"/>  <w:LsdException Locked="false" Priority="48" Name="List Table 3 Accent 6"/>  <w:LsdException Locked="false" Priority="49" Name="List Table 4 Accent 6"/>  <w:LsdException Locked="false" Priority="50" Name="List Table 5 Dark Accent 6"/>  <w:LsdException Locked="false" Priority="51"   Name="List Table 6 Colorful Accent 6"/>  <w:LsdException Locked="false" Priority="52"   Name="List Table 7 Colorful Accent 6"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Mention"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Smart Hyperlink"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Hashtag"/>  <w:LsdException Locked="false" SemiHidden="true" UnhideWhenUsed="true"   Name="Unresolved Mention"/> </w:LatentStyles></xml><![endif]--><!-- [if gte mso 10]><style> /* Style Definitions */ table.MsoNormalTable	{mso-style-name:"Table Normal";	mso-tstyle-rowband-size:0;	mso-tstyle-colband-size:0;	mso-style-noshow:yes;	mso-style-priority:99;	mso-style-parent:"";	mso-padding-alt:0in 5.4pt 0in 5.4pt;	mso-para-margin-top:0in;	mso-para-margin-right:0in;	mso-para-margin-bottom:6.0pt;	mso-para-margin-left:0in;	line-height:107%;	mso-pagination:widow-orphan;	font-size:15.0pt;	font-family:"Calibri",sans-serif;	mso-ascii-font-family:Calibri;	mso-ascii-theme-font:minor-latin;	mso-hansi-font-family:Calibri;	mso-hansi-theme-font:minor-latin;	mso-bidi-font-family:"Times New Roman";	mso-bidi-theme-font:minor-bidi;	color:#595959;	mso-themecolor:text1;	mso-themetint:166;	mso-fareast-language:JA;}</style><![endif]--> <!--StartFragment--></p><div style="mso-element: para-border-div; border: none; border-bottom: solid #56152F 1.5pt; mso-border-bottom-themecolor: accent4; padding: 0in 0in 12.0pt 0in;"><h1>Take Notes</h1></div><p class="MsoListBullet" style="mso-list: l0 level1 lfo1;"><!-- [if !supportLists]--><span style="font-family: Symbol; mso-fareast-font-family: Symbol; mso-bidi-font-family: Symbol;"><span style="mso-list: Ignore;">&middot;<span style="font: 7.0pt \'Times New Roman\';">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </span></span></span><!--[endif]-->To take notes, just tap here and start typing.</p><p class="MsoListBullet" style="mso-list: l0 level1 lfo1;"><!-- [if !supportLists]--><span style="font-family: Symbol; mso-fareast-font-family: Symbol; mso-bidi-font-family: Symbol;"><span style="mso-list: Ignore;">&middot;<span style="font: 7.0pt \'Times New Roman\';">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </span></span></span><!--[endif]-->Or, easily create a digital notebook for all your notes that automatically syncs across your devices, using the free OneNote app.</p><h2>To learn more and get OneNote, visit <span class="MsoHyperlink"><a href="http://go.microsoft.com/fwlink/?LinkID=523891">www.onenote.com</a></span>.</h2><p class="MsoNormal">&nbsp;</p><h2>Heading 2</h2><p class="MsoListParagraphCxSpFirst" style="text-indent: -.25in; mso-list: l1 level1 lfo2;"><!-- [if !supportLists]--><span style="mso-bidi-font-family: Calibri; mso-bidi-theme-font: minor-latin;"><span style="mso-list: Ignore;">1.<span style="font: 7.0pt \'Times New Roman\';">&nbsp;&nbsp;&nbsp; </span></span></span><!--[endif]-->Ordered item1</p><p class="MsoListParagraphCxSpMiddle" style="text-indent: -.25in; mso-list: l1 level1 lfo2;"><!-- [if !supportLists]--><span style="mso-bidi-font-family: Calibri; mso-bidi-theme-font: minor-latin;"><span style="mso-list: Ignore;">2.<span style="font: 7.0pt \'Times New Roman\';">&nbsp;&nbsp;&nbsp; </span></span></span><!--[endif]-->Ordered item2</p><p class="MsoListParagraphCxSpLast" style="text-indent: -.25in; mso-list: l1 level1 lfo2;"><!-- [if !supportLists]--><span style="mso-bidi-font-family: Calibri; mso-bidi-theme-font: minor-latin;"><span style="mso-list: Ignore;">3.<span style="font: 7.0pt \'Times New Roman\';">&nbsp;&nbsp;&nbsp; </span></span></span><!--[endif]-->Ordered item3 with <i style="mso-bidi-font-style: normal;">italics</i>, <b style="mso-bidi-font-weight: normal;">bold</b>, <u>underline</u>, <s>strikethrough</s>, <b style="mso-bidi-font-weight: normal;"><i style="mso-bidi-font-style: normal;"><s><u>all</u></s></i></b></p><p class="MsoNormal">&nbsp;</p><p class="MsoNormal"><span style="mso-no-proof: yes;"><!-- [if gte vml 1]><v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" o:preferrelative="t" path="m@4@5l@4@11@9@11@9@5xe" filled="f" stroked="f"> <v:stroke joinstyle="miter"/> <v:formulas>  <v:f eqn="if lineDrawn pixelLineWidth 0"/>  <v:f eqn="sum @0 1 0"/>  <v:f eqn="sum 0 0 @1"/>  <v:f eqn="prod @2 1 2"/>  <v:f eqn="prod @3 21600 pixelWidth"/>  <v:f eqn="prod @3 21600 pixelHeight"/>  <v:f eqn="sum @0 0 1"/>  <v:f eqn="prod @6 1 2"/>  <v:f eqn="prod @7 21600 pixelWidth"/>  <v:f eqn="sum @8 21600 0"/>  <v:f eqn="prod @7 21600 pixelHeight"/>  <v:f eqn="sum @10 21600 0"/> </v:formulas> <v:path o:extrusionok="f" gradientshapeok="t" o:connecttype="rect"/> <o:lock v:ext="edit" aspectratio="t"/></v:shapetype><v:shape id="Picture_x0020_1" o:spid="_x0000_i1025" type="#_x0000_t75" style=\'width:276pt;height:208pt;visibility:visible;mso-wrap-style:square\'> <v:imagedata src="file:////Users/myuser/Library/Group%20Containers/UBF8T346G9.Office/TemporaryItems/msohtmlclip/clip_image001.png"  o:title=""/></v:shape><![endif]--><!-- [if !vml]--><img src="file:////Users/myuser/Library/Group%20Containers/UBF8T346G9.Office/TemporaryItems/msohtmlclip/clip_image001.png" width="276" height="208" border="0" /><!--[endif]--></span></p><p class="MsoNormal">&nbsp;</p><p class="MsoNormal">&nbsp;</p><p><!--EndFragment--></p>',
         """<p>qwerty</p>
<h1>Take Notes</h1>
<ul>
<li>
<p>To take notes, just tap here and start typing.</p>
</li>
<li>
<p>Or, easily create a digital notebook for all your notes that automatically syncs across your devices, using the free OneNote app.</p>
</li>
</ul>
<h2>To learn more and get OneNote, visit <a href="http://go.microsoft.com/fwlink/?LinkID=523891">www.onenote.com</a>.</h2>
<h2>Heading 2</h2>
<ol>
<li>
<p>Ordered item1</p>
</li>
<li>
<p>Ordered item2</p>
</li>
<li>
<p>Ordered item3 with <em>italics</em> , <strong>bold</strong> , <em>underline</em> , ~~strikethrough~~ , <strong><em>~~_all</em>~~_</strong></p>
</li>
</ol>
<p><img src='file:////Users/myuser/Library/Group%20Containers/UBF8T346G9.Office/TemporaryItems/msohtmlclip/clip_image001.png' width='276' height='208' /></p>"""),
    )
    @ddt.unpack
    def test_clean_html(self, content, expected):
        """ Verify the method removes unnecessary HTML attributes. """
        self.maxDiff = None
        self.assertEqual(clean_html(content), expected)
