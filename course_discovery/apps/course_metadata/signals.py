import logging

import waffle
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.constants import MASTERS_PROGRAM_TYPE_SLUG
from course_discovery.apps.course_metadata.models import (
    CourseRun, Curriculum, CurriculumCourseMembership, Program, Seat
)
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

    partner = seat.course_run.course.partner

    if not partner.lms_api_client:
        logger.info(
            'LMS api client is not initiated. Cannot publish [%s] track for [%s] course_run',
            seat.type,
            seat.course_run.key,
        )
        return

    if not partner.lms_coursemode_api_url:
        logger.info(
            'No lms coursemode api url configured. Masters seat for course_run [%s] not published',
            seat.course_run.key
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


@receiver(pre_save, sender=CourseRun)
def save_course_run(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that when a course run is saved, that its external_key is
    unique.

    If the course is associated with a program through a Curriculum, we will verify that
    the external course key is unique across all programs it is assocaited with.

    If the course is not associated with a program, we will still verify that the external_key
    is unique within course runs in the course
    """
    if not instance.external_key:
        return
    if instance.id:
        old_course_run = CourseRun.objects.get(pk=instance.id)
        if instance.external_key == old_course_run.external_key:
            return

    course_run_map = {instance.external_key: instance}
    course = instance.course
    curricula = course.degree_course_curricula
    if not curricula.all().exists():
        duplicate_course_run = check_course_for_duplicate_external_key(course, course_run_map)
        if duplicate_course_run:
            message = _duplicate_external_key_message(duplicate_course_run)
            raise ValidationError(message)
    else:
        seen_courses = set()
        for curriculum in curricula.all():
            check_curriculum(curriculum, course_run_map, seen_courses)


@receiver(pre_save, sender=CurriculumCourseMembership)
def save_curriculum_course_membership(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that if a curriculum_course_membership is created or modified, the
    external_keys for the course
    """
    course_runs = instance.course.course_runs.filter(external_key__isnull=False)
    course_run_map = {
        course_run.external_key: course_run for course_run in course_runs
    }
    check_curriculum(instance.curriculum, course_run_map, set())


@receiver(pre_save, sender=Curriculum)
def save_curriculum(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that if a curriculum is created or becomes associated with a different
    program, the curriculum's external_keys are/remain unique
    """
    if instance.id and instance.program:
        old_curriculum = Curriculum.objects.get(pk=instance.id)
        if old_curriculum.program and instance.program.id == old_curriculum.program.id:
            return
    else:
        return  # If not instance.id, we can't access course_curriculum, so we can't do anything

    course_run_map = {}
    for course in instance.course_curriculum.all():
        for course_run in course.course_runs.filter(external_key__isnull=False):
            course_run_map[course_run.external_key] = course_run
    check_curriculum(instance, course_run_map, set())


def check_curriculum(curriculum, course_run_map, checked_courses):
    if curriculum.program:
        duplicate_course_key_info = check_program_for_duplicate_external_key(
            curriculum.program,
            course_run_map,
            checked_courses
        )
    else:
        duplicate_course_run = check_curriculum_for_duplicate_external_key(curriculum, course_run_map, checked_courses)
        duplicate_course_key_info = (duplicate_course_run, curriculum) if duplicate_course_run else None
    if duplicate_course_key_info:
        message = _duplicate_external_key_message(*duplicate_course_key_info)
        raise ValidationError(message)


def _duplicate_external_key_message(course_run, curriculum=None):
    message = "Duplicate external_key found: external_key={} course_run={} course={}".format(
        course_run.external_key,
        course_run,
        course_run.course
    )
    if curriculum:
        message = message + " curriculum={}".format(curriculum)
        if curriculum.program:
            message = message + " program={}".format(curriculum.program)
    return message


def check_program_for_duplicate_external_key(program, course_run_map, checked_courses):
    """
    Helper function for verifying the uniqueness of external course keys within a program

    Parameters:
        - program: program in which we are searching for potential duplicate course keys
        - external_key_map: dict mapping external course keys to their course runs.
                            These are the external course keys that we looking for potential duplicates of

    Returns:
        If a course run is found in the `course_curriculum` of a Curriculum of `program` that has the same external
        course key as a course run in `external_course_map` (but isn't the course run in `external_course_map`),
        we will return a tuple of:  (course_run, curriculum) of the 'offending' duplicate course key that we found
    """
    for curriculum in program.curricula.all():
        offending_course_run = check_curriculum_for_duplicate_external_key(curriculum, course_run_map, checked_courses)
        if offending_course_run:
            return (offending_course_run, curriculum)


def check_curriculum_for_duplicate_external_key(curriculum, course_run_map, checked_courses):
    for course in curriculum.course_curriculum.all():
        if course in checked_courses:
            continue
        offending_course_run = check_course_for_duplicate_external_key(course, course_run_map)
        if offending_course_run:
            return offending_course_run
        checked_courses.add(course)


def check_course_for_duplicate_external_key(course, course_run_map):
    """
    Helper function for verifying the uniqueness of external course keys within a course

    Parameters:
        - course: course in which we are searching for potential duplicate course keys
        - external_key_map: dict mapping external course keys to their course runs.
                            These are the external course keys that we looking for potential duplicates of

    Returns:
        If a course run is found under `course` that has the same external
        course key as a course run in `external_course_map` (but isn't the course run in `external_course_map`),
        this function will return the 'offending' course_run
    """
    for course_run in course.course_runs.all():
        external_key = course_run.external_key
        if external_key in course_run_map and course_run_map[external_key] != course_run:
            return course_run
