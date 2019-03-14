import logging

import waffle
from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from edx_rest_api_client.client import OAuthAPIClient

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.course_metadata.models import CurriculumCourseMembership, Program
from course_discovery.apps.course_metadata.publishers import ProgramMarketingSitePublisher
from course_discovery.apps.course_metadata.waffle import masters_course_mode_enabled

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Program)
def delete_program(sender, instance, **kwargs):  # pylint: disable=unused-argument
    is_publishable = (
        instance.partner.has_marketing_site and
        waffle.switch_is_active('publish_program_to_marketing_site')
    )

    if is_publishable:
        publisher = ProgramMarketingSitePublisher(instance.partner)
        publisher.delete_obj(instance)


@receiver(post_save, sender=CurriculumCourseMembership)
def add_masters_track_on_course(sender, instance, **kwargs):  # pylint: disable=unused-argument
    # When this waffle flag is enabled we api call to ensure that the 'masters' course_mode is added to
    # that course

    if masters_course_mode_enabled():
        program = instance.curriculum.program

        if program.type.slug != 'masters':
            return None

        if not program.partner.lms_commerce_api_url:
            return None

        partner = program.partner
        commerce_api_client = OAuthAPIClient(partner.lms_url, partner.oidc_key, partner.oidc_secret)

        for course_run in instance.course_runs:
            _add_masters_track_on_commerce_course_run(course_run, partner.lms_commerce_api_url, commerce_api_client)


def _add_masters_track_on_commerce_course_run(course_run, api_url, commerce_api_client):
    """ Given a course_run, api_url, and a commerce_api_client, this helper method will call the commerce api to
    add the masters track to a course run. """

    course_run_key = course_run.key
    url = api_url + 'courses/{}/'.format(course_run_key)

    data = {
        'id': course_run_key,
        'modes': _seats_for_course_run(course_run),
    }

    response = commerce_api_client.put(url, json=data)

    if response.ok:
        logger.info('Successfully published commerce data for [%s].', course_run_key)
    else:
        logger.exception(
            'Failed to add masters course_mode to course_run [%s] in commerce api to LMS.',
            course_run_key
        )


def _seats_for_course_run(course_run):
    """ Given a course run, this method serializes all current available seats and appends a masters seat. """

    seats = course_run.enrollable_seats()
    current_seat_types = [_serialize_seat_as_course_mode_for_commerce_api(seat) for seat in seats]
    return current_seat_types + [{
        'name': 'masters',
        'currency': 'usd',
        'price': 0,
        'sku': None,
        'bulk_sku': None,
        'expires': None,
    }]


def _serialize_seat_as_course_mode_for_commerce_api(seat):
    """ Serializes a course seat product to a dict that can be further serialized to JSON. """

    return {
        'name': seat.type,
        'currency': str(seat.currency.code) if seat.currency else '',
        'price': int(seat.price),
        'sku': seat.sku,
        'bulk_sku': seat.bulk_sku,
        'expires': seat.upgrade_deadline.isoformat() if seat.upgrade_deadline else None,
    }

# Invalidate API cache when any model in the course_metadata app is saved or
# deleted. Given how interconnected our data is and how infrequently our models
# change (data loading aside), this is a clean and simple way to ensure correctness
# of the API while providing closer-to-optimal cache TTLs.
for model in apps.get_app_config('course_metadata').get_models():
    for signal in (post_save, post_delete):
        signal.connect(api_change_receiver, sender=model)
