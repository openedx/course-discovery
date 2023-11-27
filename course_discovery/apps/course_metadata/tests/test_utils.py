import datetime
import json
import re
import urllib
from unittest import mock

import ddt
import pytest
import pytz
import requests
import responses
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from edx_toggles.toggles.testutils import override_waffle_switch
from slugify import slugify

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata import utils
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.constants import DEFAULT_SLUG_FORMAT_ERROR_MSG
from course_discovery.apps.course_metadata.data_loaders.utils import map_external_org_code_to_internal_org_code
from course_discovery.apps.course_metadata.exceptions import (
    EcommerceSiteAPIClientException, MarketingSiteAPIClientException
)
from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseRun, CourseType, CourseUrlSlug, Seat, SeatType, Track
)
from course_discovery.apps.course_metadata.tests.constants import MOCK_PRODUCTS_DATA
from course_discovery.apps.course_metadata.tests.factories import (
    CourseEditorFactory, CourseEntitlementFactory, CourseFactory, CourseRunFactory, CourseTypeFactory, ModeFactory,
    OrganizationFactory, OrganizationMappingFactory, PartnerFactory, ProgramFactory, SeatFactory, SeatTypeFactory,
    SourceFactory, SubjectFactory
)
from course_discovery.apps.course_metadata.tests.mixins import MarketingSiteAPIClientTestMixin
from course_discovery.apps.course_metadata.toggles import (
    IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE, IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED
)
from course_discovery.apps.course_metadata.utils import (
    calculated_seat_upgrade_deadline, clean_html, convert_svg_to_png_from_url, create_missing_entitlement,
    download_and_save_course_image, download_and_save_program_image, ensure_draft_world, fetch_getsmarter_products,
    is_google_drive_url, serialize_entitlement_for_ecommerce_api, serialize_seat_for_ecommerce_api,
    transform_skills_data, validate_slug_format
)


@ddt.ddt
class UploadToFieldNamePathTests(TestCase):
    """
    Test the utiltity object 'UploadtoFieldNamePath'
    """
    def setUp(self):
        super().setUp()
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
        assert regex.match(upload_path)


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

    def mock_publication(self, status=200, json=None):  # pylint: disable=redefined-outer-name
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
        assert utils.push_to_ecommerce_for_course_run(self.course_run)
        for s in self.seats:
            s.refresh_from_db()
        self.entitlement.refresh_from_db()
        assert {s.sku for s in self.seats} == {'XXXXXXXX', 'YYYYYYYY'}
        assert self.entitlement.sku == 'ZZZZZZZZ'

        # Check draft versions too
        assert {s.sku for s in self.course_run.draft_version.seats.all()} == {'XXXXXXXX', 'YYYYYYYY'}
        assert self.course.draft_version.entitlements.first().sku == 'ZZZZZZZZ'

    def test_status_failure(self):
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.mock_access_token()
        self.mock_publication(status=500)
        with pytest.raises(requests.HTTPError):
            utils.push_to_ecommerce_for_course_run(self.course_run)

        responses.reset()
        self.mock_publication(status=500, json={'error': 'Test error message'})
        with pytest.raises(EcommerceSiteAPIClientException):
            utils.push_to_ecommerce_for_course_run(self.course_run)

    def test_no_products(self):
        for seat in self.seats:
            seat.delete()
        self.entitlement.delete()
        assert not utils.push_to_ecommerce_for_course_run(self.course_run)

    def test_no_ecommerce_url(self):
        self.partner.ecommerce_api_url = None
        self.partner.save()
        assert not utils.push_to_ecommerce_for_course_run(self.course_run)


@ddt.ddt
class TestSerializeSeatForEcommerceApi(TestCase):
    def setUp(self):
        super().setUp()
        self.course_run_missing_variant = CourseRunFactory(variant_id=None)
        self.course_run_variant_id = CourseRunFactory(variant_id='00000000-0000-0000-0000-000000000000')

    @ddt.data(
        ('', False, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': ''},
                {'name': 'id_verification_required', 'value': False},
            ]
        }),
        ('verified', True, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': 'verified'},
                {'name': 'id_verification_required', 'value': True},
            ]
        }),
    )
    @ddt.unpack
    def test_serialize_seat_for_ecommerce_api_without_variant_id(self, certificate_type, is_id_verified, expected):
        """
        Test that serialize_seat_for_ecommerce_api returns the expected data for a seat of OCM course
        """
        seat = SeatFactory(course_run=self.course_run_missing_variant, sku='example_sku', price=100.00)
        mode = ModeFactory(certificate_type=certificate_type, is_id_verified=is_id_verified)

        actual = serialize_seat_for_ecommerce_api(seat, mode)
        expected['expires'] = serialize_datetime(calculated_seat_upgrade_deadline(seat))
        expected['price'] = str(seat.price)

        assert actual == expected

        seat.sku = None
        seat.course_run = self.course_run_missing_variant
        expected['stockrecords'][0]['partner_sku'] = None

        actual = serialize_seat_for_ecommerce_api(seat, mode)
        assert actual == expected

    @ddt.data(
        ('', False, False, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': ''},
                {'name': 'id_verification_required', 'value': False},
            ]
        }),
        ('verified', True, False, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': 'verified'},
                {'name': 'id_verification_required', 'value': True},
            ]
        }),
        ('', False, True, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': ''},
                {'name': 'id_verification_required', 'value': False},
                {'name': 'variant_id', 'value': '00000000-0000-0000-0000-000000000000'},
            ]
        }),
        ('verified', True, True, {
            'expires': 'expected_expiry_date',
            'price': '100.00',
            'product_class': 'Seat',
            'stockrecords': [{'partner_sku': 'example_sku'}],
            'attribute_values': [
                {'name': 'certificate_type', 'value': 'verified'},
                {'name': 'id_verification_required', 'value': True},
                {'name': 'variant_id', 'value': '00000000-0000-0000-0000-000000000000'},
            ]
        }),
    )
    @ddt.unpack
    def test_serialize_seat_for_ecommerce_api_with_variant_id_present(
        self, certificate_type, is_id_verified, variant_id_flag, expected
    ):
        """
        Test that serialize_seat_for_ecommerce_api returns the expected data for a seat of external LOBs course
        """
        seat = SeatFactory(course_run=self.course_run_variant_id, sku='example_sku', price=100.00)
        mode = ModeFactory(certificate_type=certificate_type, is_id_verified=is_id_verified)
        with override_waffle_switch(IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE, active=variant_id_flag):
            actual = serialize_seat_for_ecommerce_api(seat, mode)
            expected['expires'] = serialize_datetime(calculated_seat_upgrade_deadline(seat))
            expected['price'] = str(seat.price)

            assert actual == expected
            seat.sku = None
            seat.course_run = self.course_run_variant_id
            expected['stockrecords'][0]['partner_sku'] = None

            actual = serialize_seat_for_ecommerce_api(seat, mode)
            assert actual == expected


@pytest.mark.django_db
@ddt.ddt
class TestSerializeEntitlementForEcommerceApi(TestCase):
    def setUp(self):
        super().setUp()
        self.ocm_course = CourseFactory(additional_metadata=None)
        self.external_course = CourseFactory()
        CourseRunFactory(
            start=datetime.datetime(2022, 10, 13, tzinfo=pytz.UTC),
            end=datetime.datetime(2050, 3, 1, tzinfo=pytz.UTC),
            course=self.external_course,
            status=CourseRunStatus.Published,
            type__is_marketable=True,
            draft=False,
        )
        SeatFactory(course_run=self.external_course.course_runs.first(), sku='example_sku', price=100.00)

    def test_serialize_entitlement_for_ecommerce_api(self):
        """
        CourseEntitlement should be able to be serialized as expected for
        call to ecommerce api.
        """
        entitlement = CourseEntitlementFactory(course=self.ocm_course)
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

    def test_serialize_entitlement_for_ecommerce_api_additional_metadata(self):
        """
        Additional metadata should be included in attribute values sent to Ecommerce
        if they are present on a course object.
        """
        entitlement = CourseEntitlementFactory(course=self.external_course)
        actual = serialize_entitlement_for_ecommerce_api(entitlement)
        expected = {
            'price': str(entitlement.price),
            'product_class': 'Course Entitlement',
            'attribute_values': [
                {
                    'name': 'certificate_type',
                    'value': entitlement.mode.slug,
                },
                {
                    'name': 'variant_id',
                    'value': str(entitlement.course.additional_metadata.variant_id),
                },
            ]
        }

        assert actual == expected

    @ddt.data(False, True)
    def test_serialize_entitlement_for_ecommerce_api_with_variant_id_flag(
        self, variant_id_flag
    ):
        """
        Test to verify that certificate type and variant_id should be included in attribute values
        sent to Ecommerce if they are present on a course object.

        If IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE is False, variant_id is taken from course.additional_metadata
        If IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE is True, variant_id is taken from course.advertised_course_run
        """
        entitlement = CourseEntitlementFactory(course=self.external_course)
        with override_waffle_switch(IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE, active=variant_id_flag):
            actual = serialize_entitlement_for_ecommerce_api(entitlement)
            attribute_values_list = [
                {
                    'name': 'certificate_type',
                    'value': entitlement.mode.slug,
                },
            ]
            if variant_id_flag:
                course = entitlement.course
                attribute_values_list.append({
                    'name': 'variant_id',
                    'value': str(course.advertised_course_run.variant_id),
                })
            else:
                attribute_values_list.append({
                    'name': 'variant_id',
                    'value': str(entitlement.course.additional_metadata.variant_id),
                })

            expected = {
                'price': str(entitlement.price),
                'product_class': 'Course Entitlement',
                'attribute_values': attribute_values_list
            }

            assert actual == expected


class MarketingSiteAPIClientTests(MarketingSiteAPIClientTestMixin):
    """
    Unit test cases for MarketinSiteAPIClient
    """
    def setUp(self):
        super().setUp()
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
        assert session is not None

    @responses.activate
    def test_init_session_failed(self):
        self.mock_login_response(500)
        with pytest.raises(MarketingSiteAPIClientException):
            self.api_client.init_session  # pylint: disable=pointless-statement

    @responses.activate
    def test_csrf_token(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        csrf_token = self.api_client.csrf_token
        self.assert_responses_call_count(3)
        assert self.csrf_token == csrf_token

    @responses.activate
    def test_csrf_token_failed(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(500)
        with pytest.raises(MarketingSiteAPIClientException):
            self.api_client.csrf_token  # pylint: disable=pointless-statement

    @responses.activate
    def test_user_id(self):
        self.mock_login_response(200)
        self.mock_user_id_response(200)
        user_id = self.api_client.user_id
        self.assert_responses_call_count(3)
        assert self.user_id == user_id

    @responses.activate
    def test_user_id_failed(self):
        self.mock_login_response(200)
        self.mock_user_id_response(500)
        with pytest.raises(MarketingSiteAPIClientException):
            self.api_client.user_id  # pylint: disable=pointless-statement

    @responses.activate
    def test_api_session(self):
        self.mock_login_response(200)
        self.mock_csrf_token_response(200)
        api_session = self.api_client.api_session
        self.assert_responses_call_count(3)
        assert api_session is not None
        assert api_session.headers.get('Content-Type') == 'application/json'
        assert api_session.headers.get('X-CSRF-Token') == self.csrf_token

    @responses.activate
    def test_api_session_failed(self):
        self.mock_login_response(500)
        self.mock_csrf_token_response(500)
        with pytest.raises(MarketingSiteAPIClientException):
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

        assert 1 == len(CourseRun.objects.all())
        assert 2 == len(CourseRun.everything.all())

        assert draft_course_run.draft
        assert not original_course_run.draft

        if attrs:
            model_fields = [field.name for field in CourseRun._meta.get_fields()]
            diff_of_fields = list(filter(
                lambda f: getattr(original_course_run, f, None) != getattr(draft_course_run, f, None),
                model_fields
            ))
            for key, value in attrs.items():
                # Make sure that any attributes we changed are different in the draft course run from the original
                assert key in diff_of_fields
                assert getattr(draft_course_run, key) == value

    def test_set_draft_state_with_foreign_key(self):
        course = CourseFactory()
        course_run = CourseRunFactory(course=course)
        draft_course, original_course = utils.set_draft_state(course, Course)
        draft_course_run, original_course_run = utils.set_draft_state(course_run, CourseRun, {'course': draft_course})

        assert 1 == len(CourseRun.objects.all())
        assert 2 == len(CourseRun.everything.all())
        assert 1 == len(Course.objects.all())
        assert 2 == len(Course.everything.all())

        assert draft_course_run.draft
        assert not original_course_run.draft

        assert draft_course.draft
        assert not original_course.draft

        assert draft_course_run.course != original_course_run.course
        assert draft_course_run.course == draft_course
        assert original_course_run.course == original_course

    def test_ensure_draft_world_draft_obj_given(self):
        course_run = CourseRunFactory(draft=True)
        ensured_draft_course_run = utils.ensure_draft_world(course_run)

        assert ensured_draft_course_run == course_run
        assert ensured_draft_course_run.id == course_run.id
        assert ensured_draft_course_run.uuid == course_run.uuid
        assert ensured_draft_course_run.draft == course_run.draft

    def test_ensure_draft_world_not_draft_course_run_given(self):
        course = CourseFactory()
        course_run = CourseRunFactory(course=course)
        verified_seat = SeatFactory(type=SeatTypeFactory.verified(), course_run=course_run)
        audit_seat = SeatFactory(type=SeatTypeFactory.audit(), course_run=course_run)
        course_run.seats.add(verified_seat, audit_seat)

        ensured_draft_course_run = utils.ensure_draft_world(course_run)
        not_draft_course_run = CourseRun.objects.get(uuid=course_run.uuid)

        assert ensured_draft_course_run != not_draft_course_run
        assert ensured_draft_course_run.uuid == not_draft_course_run.uuid
        assert ensured_draft_course_run.draft
        assert ensured_draft_course_run.course != not_draft_course_run.course
        assert ensured_draft_course_run.course.uuid == not_draft_course_run.course.uuid

        # Check slugs are equal
        assert ensured_draft_course_run.slug == not_draft_course_run.slug

        # Seat checks
        draft_seats = ensured_draft_course_run.seats.all()
        not_draft_seats = not_draft_course_run.seats.all()
        assert draft_seats != not_draft_seats
        assert len(draft_seats) == len(not_draft_seats)
        for i, draft_seat in enumerate(draft_seats):
            assert draft_seat.price == not_draft_seats[i].price
            assert draft_seat.sku == not_draft_seats[i].sku
            assert draft_seat.course_run != not_draft_seats[i].course_run
            assert draft_seat.course_run.uuid == not_draft_seats[i].course_run.uuid
            assert draft_seat.official_version == not_draft_seats[i]
            assert not_draft_seats[i].draft_version == draft_seat

        # Check draft course is also created
        draft_course = ensured_draft_course_run.course
        not_draft_course = Course.objects.get(uuid=course.uuid)
        assert draft_course != not_draft_course
        assert draft_course.uuid == not_draft_course.uuid
        assert draft_course.draft

        # Check official and draft versions match up
        assert ensured_draft_course_run.official_version == not_draft_course_run
        assert not_draft_course_run.draft_version == ensured_draft_course_run

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

        assert ensured_draft_course != not_draft_course
        assert ensured_draft_course.uuid == not_draft_course.uuid
        assert ensured_draft_course.draft

        # Check authoring orgs are equal
        assert list(ensured_draft_course.authoring_organizations.all()) ==\
               list(not_draft_course.authoring_organizations.all())

        # Check canonical course run was updated
        assert ensured_draft_course.canonical_course_run != not_draft_course.canonical_course_run
        assert ensured_draft_course.canonical_course_run.draft
        assert ensured_draft_course.canonical_course_run.uuid == not_draft_course.canonical_course_run.uuid

        # Check course editors are moved from the official version to the draft version
        assert CourseEditor.objects.count() == 1
        assert editor.course == ensured_draft_course

        # Check course runs all share the same UUIDs, but are now all drafts
        not_draft_course_runs_uuids = [run.uuid for run in course_runs]
        draft_course_runs_uuids = [
            run.uuid for run in ensured_draft_course.course_runs.all()
        ]
        self.assertListEqual(draft_course_runs_uuids, not_draft_course_runs_uuids)

        # Entitlement checks
        draft_entitlement = ensured_draft_course.entitlements.first()
        not_draft_entitlement = not_draft_course.entitlements.first()
        assert draft_entitlement != not_draft_entitlement
        assert draft_entitlement.price == not_draft_entitlement.price
        assert draft_entitlement.sku == not_draft_entitlement.sku
        assert draft_entitlement.course != not_draft_entitlement.course
        assert draft_entitlement.course.uuid == not_draft_entitlement.course.uuid

        # check slug history not copied over
        assert ensured_draft_course.url_slug_history.count() == 0
        assert not_draft_course.url_slug_history.count() == 1

        # Check official and draft versions match up
        assert ensured_draft_course.official_version == not_draft_course
        assert not_draft_course.draft_version == ensured_draft_course

        assert draft_entitlement.official_version == not_draft_entitlement
        assert not_draft_entitlement.draft_version == draft_entitlement

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
        assert draft_entitlement.price == seat.price
        assert draft_entitlement.currency == seat.currency
        assert draft_entitlement.mode.slug == Seat.VERIFIED


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

        assert not course.entitlements.exists()
        # sanity check
        create_missing_entitlement(course)

        assert course.entitlements.count() == (1 if expected else 0)
        if expected:
            entitlement = course.entitlements.first()
            assert entitlement.mode.slug == expected[0]
            assert entitlement.price == expected[1]
            assert entitlement.currency.code == expected[2]
            assert entitlement.partner == course.partner
            assert not entitlement.draft
            # tested below

    def test_draft_course(self):
        """ Verifies that a draft course will create a draft entitlement """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory(draft=True)
        run = CourseRunFactory(course=course, end=future, enrollment_end=None, draft=True)
        seat = SeatFactory(course_run=run, type=SeatTypeFactory.verified(), draft=True)

        assert not course.entitlements.exists()
        # sanity check
        create_missing_entitlement(course)

        assert course.entitlements.count() == 1
        entitlement = course.entitlements.first()
        assert entitlement.mode.slug == Seat.VERIFIED
        assert entitlement.price == seat.price
        assert entitlement.currency == seat.currency
        assert entitlement.draft

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

        assert not course.entitlements.exists()
        # sanity check
        assert create_missing_entitlement(course)

        entitlement = course.entitlements.first()
        assert entitlement.price == date_to_price(expected)

    @mock.patch('course_discovery.apps.course_metadata.utils.push_to_ecommerce_for_course_run')
    def test_push_to_ecommerce(self, mock_push):
        """ Verifies that we push new entitlement to ecommerce """
        future = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10)
        course = CourseFactory()
        run = CourseRunFactory(course=course, end=future, enrollment_end=None)
        SeatFactory(course_run=run, type=SeatTypeFactory.verified())

        course.canonical_course_run = run
        course.save()

        assert not course.entitlements.exists()
        # sanity check
        assert create_missing_entitlement(course)

        assert mock_push.call_count == 1
        assert mock_push.call_args[0][0] == run


@ddt.ddt
class UtilsTests(TestCase):
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

        # Make sure to add target attributes to anchor tags if they are in attributes list
        # pylint: disable=line-too-long
        ('<p>please visit this <a title="less go" href="https://google.com" target="_blank" rel="noopener">link</a></p>', '<p>please visit this <a href="https://google.com" rel="noopener" target="_blank" title="less go">link</a></p>'),
        # pylint: disable=line-too-long
        ('<a href="https://yahoo.com" target="_blank" rel="noopener">link</a>', '<p><a href="https://yahoo.com" rel="noopener" target="_blank">link</a></p>'),

        # Make sure not to add data-ol-has-click-handler attribute to anchor tags if they are in attributes list
        # pylint: disable=line-too-long
        ('<p>please visit this <a title="less go" href="https://google.com" data-ol-has-click-handler="true">link</a></p>', '<p>please visit this <a href="https://google.com" title="less go">link</a></p>'),

        # And make sure we strip what we should
        ('<p class="float">Class</p>', '<p>Class</p>'),
        ('<p style="float">Inline Style</p>', '<p>Inline Style</p>'),
        ('<style>Style</style>', ''),
        ('<script>Script</script>', ''),
        ('NB&nbsp;SP', '<p>NBSP</p>'),

        # Make sure to add dir attribute to p tags if they are in attribute list
        ('<p dir="rtl" class="float">Directed paragraph</p>', '<p dir="rtl">Directed paragraph</p>'),

        # Check for ul and ol tags with dir attribute
        ('<ul dir="rtl"><li>Directed list item</li></ul>', '<ul dir="rtl">\n<li>Directed list item</li>\n</ul>'),
        ('<ol dir="rtl"><li>Directed list item</li></ol>', '<ol dir="rtl">\n<li>Directed list item</li>\n</ol>'),

        # Make sure text remains bold if p tag has rtl direction
        ('<p dir="rtl"><strong>Directed paragraph</strong></p>', '<p dir="rtl"><strong>Directed paragraph</strong></p>'),
        # Make sure the attributes on nested p tags remain as it is.
        ('<p dir="rtl"><strong lang="en" style="font-size: 11pt; color: #000000; background-color: transparent; font-weight: 400;">Test</strong></p>', '<p dir="rtl"><strong lang="en" style="font-size: 11pt; color: #000000; background-color: transparent; font-weight: 400;">Test</strong></p>'),
        # Make sure that only spans with lang tags are preserved in the saved string
        ('<p><span lang="en">with lang</span></p>', '<p><span lang="en">with lang</span></p>'),
        ('<p><span class="body" lang="en">lang and class</span></p>', '<p><span lang="en">lang and class</span></p>'),
        ('<p><span class="body">class only</span></p>', '<p>class only</p>'),

        # A sample text from real life when pasting from Microsoft Word into a rich text editor
        # pylint: disable=line-too-long
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
        ("<div><p>online course.</p><p><b></b></p><p><strong>Module 1:</strong></p></div>",
         """<p>online course.</p>
<p><strong>Module 1:</strong></p>"""),
    )
    @ddt.unpack
    def test_clean_html(self, content, expected):
        """ Verify the method removes unnecessary HTML attributes. """
        self.maxDiff = None
        assert clean_html(content) == expected

    def test_skill_data_transformation(self):
        category_data = {
            'category': {
                'name': 'Category 1'
            },
            'subcategory': {
                'name': 'Subcategory 1',
                'category': {
                    'name': 'Category 1'
                },
            }}
        input_data = [
            {
                'name': 'Skill 1',
                'description': 'Skill 1',
                **category_data
            },
            {
                'name': 'Skill 2',
                'description': 'Skill 2',
                **category_data,
                'category': None,
            }
        ]

        expected_data = [
            {
                'skill': 'Skill 1',
                'category': 'Category 1',
                'subcategory': 'Subcategory 1'
            },
            {
                'skill': 'Skill 2',
                'category': '',
                'subcategory': 'Subcategory 1'
            }
        ]

        output = transform_skills_data(input_data)
        assert output == expected_data

    def test_validate_org_map_method(self):
        partner = PartnerFactory.create(lms_url='http://127.0.0.1:8000')
        source = SourceFactory(slug='text-source', name='text-source')
        org = OrganizationFactory(name='edx', key='edx', partner=partner)
        OrganizationMappingFactory(
            organization=org, source=source, organization_external_key='ext-key'
        )
        key = map_external_org_code_to_internal_org_code('ext-key', source.slug)
        assert key == org.key


class TestConvertSvgToPngFromUrl(TestCase):
    """Test Convert SVG to PNG"""
    @mock.patch('course_discovery.apps.course_metadata.utils.svg2png')
    def test_convert_svg_to_png_from_url(self, _svg2png_mock):
        """Verify that convert_svg_to_png_from_url will return a valid value"""
        assert convert_svg_to_png_from_url('https://www.svgimageurl.com') is not None


@ddt.ddt
class TestIsGoogleDriveUrl(TestCase):
    """Test is google drive url"""
    @ddt.data(
        ('https://drive.google.com/file/d/abcd12345/view?usp=sharing', True),
        ('https://example.com/image.jpg', False),
    )
    @ddt.unpack
    def test_is_google_drive_url(self, url, expected):
        """Verify that is_google_drive_url will return a valid value"""
        assert is_google_drive_url(url) is expected


class TestDownloadAndSaveImage(TestCase):
    """ Test to download and save image """

    IMG_CONTENT = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00' \
                  b'\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00' \
                  b'IEND\xaeB`\x82'

    def mock_image_response(self, status=200, body=None, content_type='image/jpeg', url='https://example.com/image.jpg'):  # pylint: disable=line-too-long
        body = body or b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00' \
                       b'\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00' \
                       b'IEND\xaeB`\x82'
        image_url = url
        responses.add(
            responses.GET,
            image_url,
            body=body,
            status=status,
            content_type=content_type
        )
        return image_url, body

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @mock.patch('course_discovery.apps.course_metadata.utils.get_file_from_drive_link')
    def test_download_and_save_course_image__using_drive_link(self, mock_get_file_from_drive_link, mock_logger):
        """ Verify that download_and_save_course_image will save image in course model using drive link """
        image_url = 'https://drive.google.com/file/d/abcd12345/view?usp=sharing'
        data_field = 'image'
        course = CourseFactory(card_image_url=image_url, image=None)
        mock_get_file_from_drive_link.return_value = ('image/jpeg', self.IMG_CONTENT)
        assert download_and_save_course_image(
            course, course.card_image_url, data_field=data_field, headers=None) is True
        mock_logger.info.assert_called_with(
            f'Image for course {course.key} successfully updated in {data_field} field'
        )
        mock_get_file_from_drive_link.assert_called_once_with(course.card_image_url)
        course.refresh_from_db()
        assert course.card_image_url == image_url
        assert course.image is not None
        assert course.image.read() == self.IMG_CONTENT
        assert str(course.uuid) in course.image.name

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @responses.activate
    def test_download_and_save_course_image__using_request_library(self, mock_logger):
        """ Verify that download_and_save_course_image will save image in course model using request response """
        image_url = 'https://example.com/image.jpg'
        data_field = 'image'
        course = CourseFactory(card_image_url=image_url, image=None)
        image_url, content = self.mock_image_response()
        assert download_and_save_course_image(course, course.card_image_url, data_field='image', headers=None) is True
        mock_logger.info.assert_called_with(
            f'Image for course {course.key} successfully updated in {data_field} field'
        )
        course.refresh_from_db()
        assert course.card_image_url == image_url
        assert course.image is not None
        assert course.image.read() == content
        assert str(course.uuid) in course.image.name

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @mock.patch('course_discovery.apps.course_metadata.utils.get_file_from_drive_link')
    @responses.activate
    def test_download_and_save_course_image__with_invalid_content_type_using_drive_link(self, mock_get_file_from_drive_link, mock_logger):  # pylint: disable=line-too-long
        """ Verify that download_and_save_course_image will not save image in course model """
        image_url = 'https://drive.google.com/file/d/abcd12345/view?usp=sharing'
        course = CourseFactory(card_image_url=image_url, image=None)
        content_type, content = ('text/plain', b'invalid')
        mock_get_file_from_drive_link.return_value = (content_type, content)
        assert download_and_save_course_image(course, course.card_image_url, data_field='image', headers=None) is False
        mock_logger.error.assert_called_with(
            'Image retrieved for course [%s] from [%s] has an unknown content type [%s] and will not be saved.',
            course.key, course.card_image_url, content_type
        )
        mock_get_file_from_drive_link.assert_called_once_with(course.card_image_url)
        course.refresh_from_db()
        assert course.card_image_url == image_url
        assert course.image.name == ''
        assert not bool(course.image)

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @responses.activate
    def test_download_and_save_course_image__with_invalid_content_type_using_request_library(self, mock_logger):
        """ Verify that download_and_save_course_image will not save image in course model """
        image_url = 'https://www.example.com/image.pdf'
        course = CourseFactory(card_image_url=image_url, image=None)
        image_url, _ = self.mock_image_response(status=200, body=b'invalid', content_type='text/plain', url=image_url)
        assert download_and_save_course_image(course, course.card_image_url, data_field='image', headers=None) is False
        mock_logger.error.assert_called_with(
            'Image retrieved for course [%s] from [%s] has an unknown content type [%s] and will not be saved.',
            course.key, course.card_image_url, 'text/plain'
        )
        course.refresh_from_db()
        assert course.card_image_url == image_url
        assert course.image.name == ''
        assert not bool(course.image)

    @mock.patch('course_discovery.apps.course_metadata.utils.get_file_from_drive_link')
    def test_download_and_save_program_image__using_drive_link(self, mock_get_file_from_drive_link):
        """ Verify that download_and_save_program_image will save image in program model """
        image_url = 'https://drive.google.com/file/d/abcd12345/view?usp=sharing'
        program = ProgramFactory(card_image_url=image_url, card_image=None)
        mock_get_file_from_drive_link.return_value = ('image/jpeg', self.IMG_CONTENT)
        assert download_and_save_program_image(program, program.card_image_url, data_field='image', headers=None) is True  # pylint: disable=line-too-long
        mock_get_file_from_drive_link.assert_called_once_with(program.card_image_url)
        program.refresh_from_db()
        assert program.card_image_url == image_url
        assert program.card_image is not None
        assert program.card_image.read() == self.IMG_CONTENT
        assert str(program.uuid) in program.card_image.name

    @responses.activate
    def test_download_and_save_program_image__using_request_library(self):
        """ Verify that download_and_save_program_image will save image in program model using request response """
        image_url = 'https://example.com/image.jpg'
        program = ProgramFactory(card_image_url=image_url, card_image=None)
        image_url, content = self.mock_image_response(url=image_url)
        assert download_and_save_program_image(program, program.card_image_url, data_field='image', headers=None) is True  # pylint: disable=line-too-long
        program.refresh_from_db()
        assert program.card_image_url == image_url
        assert program.card_image is not None
        assert program.card_image.read() == content
        assert str(program.uuid) in program.card_image.name

    @mock.patch('course_discovery.apps.course_metadata.utils.get_file_from_drive_link')
    def test_download_and_save_program_image__with_invalid_content_type_using_drive_link(self, mock_get_file_from_drive_link):  # pylint: disable=line-too-long
        """ Verify that download_and_save_program_image will not save image in program model using drive link """
        image_url = 'https://drive.google.com/file/d/abcd12345/view?usp=sharing'
        program = ProgramFactory(card_image_url=image_url, card_image=None)
        assert download_and_save_program_image(program, program.card_image_url, data_field='image', headers=None) is False  # pylint: disable=line-too-long
        mock_get_file_from_drive_link.assert_called_once_with(program.card_image_url)
        mock_get_file_from_drive_link.return_value = (b'invalid', 'text/plain')
        program.refresh_from_db()
        assert program.card_image_url == image_url
        assert program.card_image.name == ''
        assert not bool(program.card_image)

    @responses.activate
    def test_download_and_save_program_image__with_invalid_content_type_using_request_library(self):
        """ Verify that download_and_save_program_image will not save image in program model using request response """
        image_url = 'https://www.example.com/image.pdf'
        program = ProgramFactory(card_image_url=image_url, card_image=None)
        image_url, _ = self.mock_image_response(status=200, body=b'invalid', content_type='text/plain', url=image_url)
        assert download_and_save_program_image(program, program.card_image_url, data_field='image', headers=None) is False  # pylint: disable=line-too-long
        program.refresh_from_db()
        assert program.card_image_url == image_url
        assert program.card_image.name == ''
        assert not bool(program.card_image)

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @responses.activate
    def test_download_and_save_course_image__for_organization_logo_override_using_request_library(self, mock_logger):
        """
        Verify that download_and_save_course_image will save image in course model
        for organization_logo_override using request response
        """
        image_url = 'https://www.example.com/image.jpg'
        data_field = 'organization_logo_override'
        course = CourseFactory(card_image_url=image_url, image=None)
        image_url, content = self.mock_image_response(url=image_url)
        assert download_and_save_course_image(course, course.card_image_url, data_field=data_field) is True
        mock_logger.info.assert_called_once_with(
            f'Image for course {course.key} successfully updated in {data_field} field'
        )
        course.refresh_from_db()
        assert course.card_image_url == image_url
        assert course.organization_logo_override.read() == content
        assert course.organization_logo_override is not None
        assert str(course.uuid) in course.organization_logo_override.name

    @mock.patch('course_discovery.apps.course_metadata.utils.logger')
    @mock.patch('course_discovery.apps.course_metadata.utils.get_file_from_drive_link')
    def test_download_and_save_course_image__for_organization_logo_override_using_drive_link(self, mock_get_file_from_drive_link, mock_logger):  # pylint: disable=line-too-long
        """
        Verify that download_and_save_course_image will save image in course model
        for organization_logo_override using drive link
        """
        image_url = 'https://drive.google.com/file/d/abcd12345/view?usp=sharing'
        data_field = 'organization_logo_override'
        course = CourseFactory(card_image_url=image_url, image=None)
        mock_get_file_from_drive_link.return_value = ('image/png', self.IMG_CONTENT)
        assert download_and_save_course_image(course, course.card_image_url, data_field=data_field) is True
        mock_logger.info.assert_called_once_with(
            f'Image for course {course.key} successfully updated in {data_field} field'
        )
        mock_get_file_from_drive_link.assert_called_once_with(course.card_image_url)
        course.refresh_from_db()
        assert course.organization_logo_override is not None
        assert course.organization_logo_override.read() == self.IMG_CONTENT
        assert str(course.uuid) in course.organization_logo_override.name


class TestGEAGApiProductDetails(TestCase):
    """
    Test for GEAG API Product Details using getsmarter_api_client
    """
    SUCCESS_API_RESPONSE = {
        'products': MOCK_PRODUCTS_DATA
    }

    def tearDown(self):
        responses.reset()
        super().tearDown()

    def mock_product_api_call(self):
        """
        Mock product api with success response.
        """
        responses.add(
            responses.GET,
            settings.PRODUCT_API_URL + '/?detail=2',
            body=json.dumps(self.SUCCESS_API_RESPONSE),
            status=200,
        )
        return self.SUCCESS_API_RESPONSE

    @responses.activate
    @mock.patch('course_discovery.apps.course_metadata.utils.logger.info')
    @mock.patch('course_discovery.apps.course_metadata.utils.GetSmarterEnterpriseApiClient')
    def test_fetch_getsmarter_products__with_valid_credentials(self, mock_getsmarter_api_client, mock_logger):
        """
        Verify that get_products_details_using_getsmarter_client will return product details using getsmarter_api_client
        """
        mock_getsmarter_api_client.return_value.request.return_value.json.return_value = self.mock_product_api_call()
        products = fetch_getsmarter_products()
        assert products == self.SUCCESS_API_RESPONSE['products']
        mock_logger.assert_called_with(f"Products found in API response: {len(products)}")

    @mock.patch('course_discovery.apps.course_metadata.utils.logger.error')
    @mock.patch('course_discovery.apps.course_metadata.utils.GetSmarterEnterpriseApiClient')
    def test_fetch_getsmarter_products__with_invalid_credentials(self, mock_getsmarter_api_client, mock_logger):
        """
        Verify that get_products_details_using_getsmarter_client will return empty product details list
        """
        exception_message = 'can only concatenate str (not "NoneType") to str'
        mock_getsmarter_api_client.return_value.request.side_effect = mock.Mock(side_effect=Exception(f'{exception_message}'))  # pylint: disable=line-too-long
        products = fetch_getsmarter_products()
        mock_logger.assert_called_with(f'Failed to retrieve products from getsmarter API: {exception_message}')
        assert products == []


@ddt.ddt
class CourseSlugMethodsTests(TestCase):
    """
    Test the methods related to course slugs
    """

    @ddt.data(
        ('learn/primary-subject/organization-course-title', True, True),
        ('learn/some-text/some-text-some-text', True, True),
        ('learn/', False, True),
        ('/learn/', False, True),
        ('/media/', False, True),
        ('media/primary-subject/organization_name-course_title', False, True),
        ('learn2/primary-subject/organization-name-course-title', False, True),
        ('learn', True, False),
        ('/learn/', False, False),
        ('welcome-to-python', True, False),
        ('learn/subject_with_underscore/organization_name-course_title', True, True),
        ('test/learn/subject_with_underscore/organization_name-course_title', False, True),
    )
    @ddt.unpack
    def test_is_valid_slug_format_with_active_waffle_flag(self, text, expected_response, waffle_flag_active_value):
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=waffle_flag_active_value):
            response = utils.is_valid_slug_format(text)
            assert response == expected_response

    @ddt.data(
        ('f0392cca-886e-449d-b978-b09de1154745', True),
        ('some-random-text-sometext-449d-b978-b09de1154745', False),
        ('false_text', False),
    )
    @ddt.unpack
    def test_is_valid_uuid(self, text, expected_response):
        response = utils.is_valid_uuid(text)
        assert response == expected_response

    def test_get_slug_for_course(self):
        course = CourseFactory(title='test-title')
        slug, error = utils.get_slug_for_course(course)
        assert slug is None
        assert error == f"Course with uuid {course.uuid} and title {course.title} does not have any authoring " \
                        f"organizations"

        organization = OrganizationFactory(name='test-organization')
        course.authoring_organizations.add(organization)
        slug, error = utils.get_slug_for_course(course)
        assert slug is None
        assert error == f"Course with uuid {course.uuid} and title {course.title} does not have any subject"

        subject = SubjectFactory(name='business')
        course.subjects.add(subject)
        slug, error = utils.get_slug_for_course(course)
        assert error is None
        assert slug == f"learn/{subject.slug}/{organization.name}-{course.active_url_slug}"

    def test_get_slug_for_exec_ed_course(self):
        """
        It will verify that slug are generated correctly for executive education courses
        """
        ee_type_2u = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        course = CourseFactory(title='test-title', type=ee_type_2u)
        slug, error = utils.get_slug_for_course(course)
        assert slug is None
        assert error == f"Course with uuid {course.uuid} and title {course.title} does not have any authoring " \
                        f"organizations"

        organization = OrganizationFactory(name='test-organization')
        course.authoring_organizations.add(organization)
        slug, error = utils.get_slug_for_course(course)

        assert error is None
        assert slug == f"executive-education/{organization.name}-{slugify(course.title)}"

    def test_get_slug_for_bootcamp_course__raise_error_for_bootcamp_with_no_authoring_org(self):
        """
        It will verify that slug aren't generated for bootcamp courses with no authoring org and error is raised
        """
        bootcamp_type = CourseTypeFactory(slug=CourseType.BOOTCAMP_2U)
        course = CourseFactory(title='test-bootcamp', type=bootcamp_type)
        slug, error = utils.get_slug_for_course(course)
        assert slug is None
        assert error == f"Course with uuid {course.uuid} and title {course.title} does not have any authoring " \
            f"organizations"

    def test_get_slug_for_bootcamp_course(self):
        """
        It will verify that slug are generated correctly for bootcamp courses
        """
        bootcamp_type = CourseTypeFactory(slug=CourseType.BOOTCAMP_2U)
        course = CourseFactory(title='test-bootcamp', type=bootcamp_type, organization_short_code_override='')
        org = OrganizationFactory(name='test-organization')
        course.authoring_organizations.add(org)

        slug, error = utils.get_slug_for_course(course)
        subject = SubjectFactory(name='business')
        course.subjects.add(subject)
        slug, error = utils.get_slug_for_course(course)

        assert error is None
        assert slug == f"boot-camps/{subject.slug}/{org.name}-{slugify(course.title)}"

    def test_get_slug_for_bootcamp_course__organization_short_code_override(self):
        """
        It will verify that during slug creation it will give priority to organization_short_code_override if it exists
        otherwise it will use organization name
        """
        bootcamp_type = CourseTypeFactory(slug=CourseType.BOOTCAMP_2U)
        course = CourseFactory(title='test-bootcamp', type=bootcamp_type, organization_short_code_override='')
        org = OrganizationFactory(name='test-organization')
        course.authoring_organizations.add(org)
        subject = SubjectFactory(name='business')
        course.subjects.add(subject)
        slug, error = utils.get_slug_for_course(course)

        assert error is None
        assert slug == f"boot-camps/{subject.slug}/{org.name}-{slugify(course.title)}"
        org_short_code_override = 'org_override'
        course.organization_short_code_override = org_short_code_override
        course.save()
        slug, error = utils.get_slug_for_course(course)
        assert error is None
        assert slug == f"boot-camps/{subject.slug}/{org_short_code_override}-{slugify(course.title)}"

    def test_get_slug_for_course__with_no_url_slug(self):
        course = CourseFactory(title='test-title')
        subject = SubjectFactory(name='business')
        course.subjects.add(subject)
        organization = OrganizationFactory(name='test-organization')
        course.authoring_organizations.add(organization)
        CourseUrlSlug.objects.filter(course=course).delete()
        slug, error = utils.get_slug_for_course(course)
        assert error is None
        assert slug == f"learn/{subject.slug}/{organization.name}-{course.title}"

    def test_get_slug_for_course__with_existing_url_slug(self):
        partner = PartnerFactory()
        course1 = CourseFactory(title='test-title')
        subject = SubjectFactory(name='business')
        course1.subjects.add(subject)
        organization = OrganizationFactory(name='test-organization')
        course1.authoring_organizations.add(organization)
        course1.partner = partner
        course1.save()
        CourseUrlSlug.objects.filter(course=course1).delete()
        slug, error = utils.get_slug_for_course(course1)
        course1.set_active_url_slug(slug)

        # duplicate a new course with same title, subject and organization
        course2 = CourseFactory(title='test-title')
        subject = SubjectFactory(name='business')
        course2.subjects.add(subject)
        organization = OrganizationFactory(name='test-organization')
        course2.authoring_organizations.add(organization)
        course2.partner = partner
        course2.save()
        CourseUrlSlug.objects.filter(course=course2).delete()
        slug, error = utils.get_slug_for_course(course2)
        assert error is None
        assert slug == f"learn/{subject.slug}/{organization.name}-{course2.title}-2"

        course2.set_active_url_slug(slug)
        # duplicate a new course with same title, subject and organization
        course3 = CourseFactory(title='test-title')
        subject = SubjectFactory(name='business')
        course3.subjects.add(subject)
        organization = OrganizationFactory(name='test-organization')
        course3.authoring_organizations.add(organization)
        course3.partner = partner
        course3.save()
        CourseUrlSlug.objects.filter(course=course3).delete()
        slug, error = utils.get_slug_for_course(course3)
        assert error is None
        assert slug == f"learn/{subject.slug}/{organization.name}-{course3.title}-3"

    def test_get_slug_for_exec_ed_course__with_existing_url_slug(self):
        ee_type_2u = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        partner = PartnerFactory()
        course1 = CourseFactory(title='test-title', type=ee_type_2u)
        organization = OrganizationFactory(name='test-organization')
        course1.authoring_organizations.add(organization)
        course1.partner = partner
        course1.save()
        CourseUrlSlug.objects.filter(course=course1).delete()
        slug, error = utils.get_slug_for_course(course1)
        assert error is None
        assert slug == f"executive-education/{organization.name}-{slugify(course1.title)}"

        course1.set_active_url_slug(slug)
        # duplicate a new course with same title, subject and organization
        course2 = CourseFactory(title='test-title', type=ee_type_2u)
        organization = OrganizationFactory(name='test-organization')
        course2.authoring_organizations.add(organization)
        course2.partner = partner
        course2.save()
        CourseUrlSlug.objects.filter(course=course2).delete()
        slug, error = utils.get_slug_for_course(course2)
        assert error is None
        assert slug == f"executive-education/{organization.name}-{slugify(course2.title)}-2"

        course2.set_active_url_slug(slug)
        # duplicate a new course with same title, subject and organization
        course3 = CourseFactory(title='test-title', type=ee_type_2u)
        organization = OrganizationFactory(name='test-organization')
        course3.authoring_organizations.add(organization)
        course3.partner = partner
        course3.save()
        CourseUrlSlug.objects.filter(course=course3).delete()
        slug, error = utils.get_slug_for_course(course3)
        assert error is None
        assert slug == f"executive-education/{organization.name}-{slugify(course2.title)}-3"

    def test_get_slug_for_bootcamp_course__with_existing_url_slug(self):
        """
        Test for bootcamp course with existing subdirectory url slug
        """
        bootcamp_type = CourseTypeFactory(slug=CourseType.BOOTCAMP_2U)
        partner = PartnerFactory()
        subject = SubjectFactory(name='business')
        org = OrganizationFactory(name='test-organization')

        # Create and test multiple courses with the same title, subject, and organization
        for i in range(1, 3):
            course = CourseFactory(
                title='test-title', type=bootcamp_type, partner=partner, organization_short_code_override=''
            )
            course.authoring_organizations.add(org)
            course.subjects.add(subject)
            course.save()
            CourseUrlSlug.objects.filter(course=course).delete()
            slug, error = utils.get_slug_for_course(course)
            assert error is None
            if i == 1:
                assert slug == f"boot-camps/{subject.slug}/{org.name}-{slugify(course.title)}"
            else:
                assert slug == f"boot-camps/{subject.slug}/{org.name}-{slugify(course.title)}-{i}"
            course.set_active_url_slug(slug)

    def test_get_existing_slug_count(self):
        course1 = CourseFactory(title='test-title')
        slug = 'learn/business/test-organization-test-title'
        CourseUrlSlug.objects.filter(course=course1).delete()
        course1.set_active_url_slug(slug)

        # duplicate a new course with same title, subject and organization
        course2 = CourseFactory(title='test-title')
        CourseUrlSlug.objects.filter(course=course2).delete()
        course2.set_active_url_slug(f"{slug}-2")
        # duplicate a new course with same title, subject and organization
        course3 = CourseFactory(title='test-title')
        CourseUrlSlug.objects.filter(course=course3).delete()
        assert utils.get_existing_slug_count(slug) == 2


@ddt.ddt
class ValidateSlugFormatTest(TestCase):
    """
    Test suite for validate_slug_format method
    """
    def setUp(self):
        self.product_source = SourceFactory(slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG)
        self.external_product_source = SourceFactory(slug=settings.EXTERNAL_PRODUCT_SOURCE_SLUG)
        self.bootcamp_course_type = CourseTypeFactory(slug=CourseType.BOOTCAMP_2U)
        self.exec_ed_course_type = CourseTypeFactory(slug=CourseType.EXECUTIVE_EDUCATION_2U)
        self.test_course_1 = CourseFactory(title='test-title', product_source=self.product_source)
        self.test_course_2 = CourseFactory(title='test-title-2')
        self.test_course_3 = CourseFactory(title='test-title-3', product_source=self.product_source)
        self.test_course_4 = CourseFactory(
            title='test-title-4', product_source=self.external_product_source, type=self.exec_ed_course_type
        )
        self.bootcamp_course = CourseFactory(
            title='bootcamp-course', product_source=self.external_product_source, type=self.bootcamp_course_type
        )

        CourseRunFactory(course=self.test_course_1, status=CourseRunStatus.Published)
        CourseRunFactory(course=self.test_course_2, status=CourseRunStatus.InternalReview)
        CourseRunFactory(course=self.test_course_3, status=CourseRunStatus.Unpublished)

    @ddt.data(
        ('learn/physics/applied-physics', None, True),
        # will make this false once we will migrate all the OCM courses to new slug format
        ('learn-course', None, True),
        ('learn-course', None, False),
        ('learn-123', None, False),
    )
    @ddt.unpack
    def test_validate_slug_format__for_ocm_course(self, slug, expected_result, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format to check if the slug is in the correct format for OCM course
        with course runs past/in their review phase.
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            assert validate_slug_format(slug, self.test_course_1) is expected_result

    @ddt.data(
        ('learn/physics/applied-physics', None, True),
        ('learn-course', None, True),
        ('learn-course', None, False),
    )
    @ddt.unpack
    def test_validate_slug_format__for_unpublished_ocm_course(self, slug, expected_result, is_subdirectory_slug_format_active):  # pylint: disable=line-too-long
        """
        Test that validate_slug_format to check if the slug is in the correct format for unpublished OCM course to make
        sure that it is allowing both the slug formats
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            assert validate_slug_format(slug, self.test_course_3) is expected_result

    @ddt.data(
        ('learn-physics', None, True),
        ('learn-physics', None, False),
    )
    @ddt.unpack
    def test_validate_slug_format__for_non_ocm_course(self, slug, expected_result, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format to check if the slug is in the correct format for non OCM course
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            assert validate_slug_format(slug, self.test_course_2) is expected_result

    @ddt.data(
        ('learn/physics/applied-physics', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
        (
            'learn/', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.DEFAULT_PRODUCT_SOURCE_SLUG]['default']['error_msg']
        ),
        ('learn/', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
        (
            'learn/123', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.DEFAULT_PRODUCT_SOURCE_SLUG]['default']['error_msg']
        ),
        ('learn/123', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
        (
            'learn/physics/applied-physics/', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.DEFAULT_PRODUCT_SOURCE_SLUG]['default']['error_msg']
        ),
        ('learn$', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
    )
    @ddt.unpack
    def test_validate_slug_format__raise_exception_for_ocm_course(
        self, slug, is_subdirectory_slug_format_active, expected_error_message
    ):
        """
        Test that validate_slug_format raises exception if the slug is not in the correct format for OCM course
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            with self.assertRaises(ValidationError) as context:
                validate_slug_format(slug, self.test_course_1)

            expected_error_message = expected_error_message.format(url_slug=slug)

            actual_error_message = str(context.exception)
            self.assertIn(expected_error_message, actual_error_message)

    @ddt.data(
        ('learn/physics/applied-physics', False),
        ('learn/physics/applied-physics/', True),
        ('learn/physics/applied-physics/', False),
        ('learn/physics/applied-physics/123', True),
        ('learn/', True),
        ('learn/', False),
        ('learn$', False),
    )
    @ddt.unpack
    def test_validate_slug_format__raise_exception_for_non_ocm_course(self, slug, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format raises exception if the slug is not in the correct format for non OCM course
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            with self.assertRaises(ValidationError) as context:
                validate_slug_format(slug, self.test_course_2)

            expected_error_message = 'Enter a valid “slug” consisting of letters, numbers, underscores or hyphens.'
            actual_error_message = str(context.exception)
            self.assertIn(expected_error_message, actual_error_message)

    @ddt.data(
        ('executive-education/org-name-course-name', True),
        ('executive-education/new-org-applied-physics', True),
        ('custom-slug', True),
        ('custom-slug', False),
    )
    @ddt.unpack
    def test_validate_slug_format__for_exec_ed_course(self, slug, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format to check if the slug is in correct format for executive education courses
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            assert validate_slug_format(slug, self.test_course_4) is None

    @ddt.data(
        ('executive-education/org-name-course-name', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
        (
            'executive-education/org-name-course-name/', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.EXTERNAL_PRODUCT_SOURCE_SLUG]
            .get('executive-education-2u').get('error_msg')
        ),
        ('executive-education/org-name-course-name/', False, DEFAULT_SLUG_FORMAT_ERROR_MSG),
        (
            'executive-education/org-name-course-name/123', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.EXTERNAL_PRODUCT_SOURCE_SLUG]
            ['executive-education-2u']['error_msg']
        ),
        (
            'learn/test-course', True,
            settings.COURSE_URL_SLUGS_PATTERN[settings.EXTERNAL_PRODUCT_SOURCE_SLUG]
            ['executive-education-2u']['error_msg']
        ),
    )
    @ddt.unpack
    def test_validate_slug_format__raise_exception_for_for_exec_ed_course(
        self, slug, is_subdirectory_slug_format_active, expected_error_message
    ):
        """
        Test that validate_slug_format raises exception if the slug is not in the correct format
        for executive education courses
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            with self.assertRaises(ValidationError) as context:
                validate_slug_format(slug, self.test_course_4)

            expected_error_message = expected_error_message.format(url_slug=slug)
            actual_error_message = str(context.exception)
            self.assertIn(expected_error_message, actual_error_message)

    @ddt.data(
        ('boot-camps/physics/edx-applied-physics', True),
        ('boot-camps/python/harvard-python-for-beginners', True),
        ('custom-slug', True),
        ('custom-slug', False),
    )
    @ddt.unpack
    def test_validate_slug_format__for_bootcamps(self, slug, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format to check if the slug is in correct format for bootcamps
        """
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            assert validate_slug_format(slug, self.bootcamp_course) is None

    @ddt.data(
        ('boot-camps/primary-subject/org-name-course-name', False),
        ('boot-camps/primary-subject/org-name-course-name/', True),
        ('boot-camps/primary-subject/org-name-course-name/', False),
        ('boot-camps/org-name-course-name', True),
        ('learn/test-course', True),
    )
    @ddt.unpack
    def test_validate_slug_format__raise_exception_for_bootcamp_course(self, slug, is_subdirectory_slug_format_active):
        """
        Test that validate_slug_format raises exception if the slug is not in the correct format
        for bootcamp courses
        """
        expected_error_message = None

        if is_subdirectory_slug_format_active:
            expected_error_message = (
                settings.COURSE_URL_SLUGS_PATTERN[settings.EXTERNAL_PRODUCT_SOURCE_SLUG]
                .get('bootcamp-2u').get('error_msg')
            )
        else:
            expected_error_message = DEFAULT_SLUG_FORMAT_ERROR_MSG

        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=is_subdirectory_slug_format_active):
            with self.assertRaises(ValidationError) as context:
                validate_slug_format(slug, self.bootcamp_course)

            expected_error_message = expected_error_message.format(url_slug=slug)
            actual_error_message = str(context.exception)
            self.assertIn(expected_error_message, actual_error_message)
