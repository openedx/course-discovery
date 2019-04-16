import logging

from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

import waffle
from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.constants import MASTERS_PROGRAM_TYPE_SLUG
from course_discovery.apps.course_metadata.models import CurriculumCourseMembership, Program, Seat
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


def is_program_masters(program):
    return program and program.type.slug == MASTERS_PROGRAM_TYPE_SLUG


@receiver(post_save, sender=CurriculumCourseMembership)
def add_masters_track_on_course(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    When this waffle flag is enabled we save a "masters" seat type into the included course_runs of
    the related course
    """

    if masters_course_mode_enabled():
        program = instance.curriculum.program

        if not is_program_masters(program):
            logger.debug('This is a course related only to non-masters program. No need to create Masters seat')
            return

        us_currency = Currency.objects.get(code='USD')

        for course_run in instance.course_runs:
            Seat.objects.update_or_create(
                course_run=course_run,
                type=Seat.MASTERS,
                currency=us_currency,
            )


def get_related_masters_program(course_run):
    curriculum_memberships = course_run.course.curriculum_course_membership.all()
    for membership in curriculum_memberships:
        if is_program_masters(membership.curriculum.program) and course_run in membership.course_runs:
            return membership.curriculum.program


@receiver(post_save, sender=Seat)
def publish_masters_track(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    We should only publish the Masters track of the seat in the course_run,
    if the course_run is part of a Program of Masters type. Publish means we will
    call the commerce api on LMS to make sure LMS course_run object have the
    masters enrollment_mode created
    """
    seat = instance
    if seat.type != Seat.MASTERS:
        logger.debug('Not going to publish non masters seats')
        return

    if not masters_course_mode_enabled():
        logger.debug('Masters course mode waffle flag is not enabled')
        return

    related_masters = get_related_masters_program(seat.course_run)

    if related_masters:
        partner = related_masters.partner

        if not partner.lms_api_client:
            logger.info(
                'LMS api client is not initiated. Cannot publish [%s] track for [%s] program',
                seat.type,
                related_masters.title
            )
            return

        if not partner.lms_coursemode_api_url:
            logger.info(
                'No lms coursemode api url configured. Masters seat for program [%s] not published',
                related_masters.title
            )
            return

        _create_masters_track_on_lms_if_necessary(seat, partner)


def _create_masters_track_on_lms_if_necessary(seat, partner):
    """
    Given a seat, the partner object, this helper method will call the course mode api to
    create the masters track to a course run, if the masters track isn't already created
    """
    course_run_key = seat.course_run.key
    url = partner.lms_coursemode_api_url.rstrip('/') + '/courses/{}/'.format(course_run_key)
    get_response = partner.lms_api_client.get(url)
    if _seat_type_exists(get_response.json(), Seat.MASTERS):
        logger.info('Creating [{}] track on LMS for [{}] while it already have the track.'.format(
            seat.type,
            course_run_key,
        ))
        return

    data = {
        'course_id': seat.course_run.key,
        'mode_slug': seat.type,
        'mode_display_name': seat.type.capitalize(),
        'currency': str(seat.currency.code) if seat.currency else '',
        'min_price': int(seat.price),
    }

    response = partner.lms_api_client.post(url, json=data)

    if response.ok:
        logger.info('Successfully published [%s] seat data for [%s].', seat.type, course_run_key)
    else:
        logger.exception(
            'Failed to add [%s] course_mode to course_run [%s] in course_mode api to LMS.',
            seat.type,
            course_run_key
        )


def _seat_type_exists(course_modes, seat_type):
    """
    Check if a seat of the specified seat_type already exist within the list passed in.
    """
    for course_mode in course_modes:
        if course_mode['mode_slug'] == seat_type:
            return True
    return False


# Invalidate API cache when any model in the course_metadata app is saved or
# deleted. Given how interconnected our data is and how infrequently our models
# change (data loading aside), this is a clean and simple way to ensure correctness
# of the API while providing closer-to-optimal cache TTLs.
for model in apps.get_app_config('course_metadata').get_models():
    for signal in (post_save, post_delete):
        signal.connect(api_change_receiver, sender=model)
