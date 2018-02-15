import pytest

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.publisher.api.utils import (serialize_entitlement_for_ecommerce_api,
                                                       serialize_seat_for_ecommerce_api)
from course_discovery.apps.publisher.models import Seat
from course_discovery.apps.publisher.tests.factories import CourseEntitlementFactory, SeatFactory


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
            'expires': serialize_datetime(seat.calculated_upgrade_deadline),
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
                    'value': entitlement.mode,
                },
            ]
        }

        assert actual == expected
