from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.publisher.models import Seat


def serialize_seat_for_ecommerce_api(seat):
    return {
        'expires': serialize_datetime(seat.calculated_upgrade_deadline),
        'price': str(seat.price),
        'product_class': 'Seat',
        'attribute_values': [
            {
                'name': 'certificate_type',
                'value': None if seat.type == Seat.AUDIT else seat.type,
            },
            {
                'name': 'id_verification_required',
                'value': seat.type in (Seat.VERIFIED, Seat.PROFESSIONAL),
            }
        ]
    }
