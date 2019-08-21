import logging

import waffle
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.constants import MASTERS_PROGRAM_TYPE_SLUG
from course_discovery.apps.course_metadata.models import (
    CourseRun, Curriculum, CurriculumCourseMembership, CurriculumProgramMembership, Program, Seat
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


@receiver(pre_save, sender=Curriculum)
def save_curriculum(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Check for circular references in program structure before saving.
    Short circuits on:
        - newly created Curriculum since it cannot have member programs yet
        - Curriculum with a 'None' program since there cannot be a loop
    """
    curriculum = instance
    if not curriculum.id or not curriculum.program:
        return

    if _find_in_programs(curriculum.program_curriculum.all(), program=curriculum.program):
        raise ValidationError('Circular ref error.  Curriculum already contains program {}'.format(curriculum.program))


@receiver(pre_save, sender=CurriculumProgramMembership)
def save_curriculum_program_membership(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Check for circular references in program structure before saving.
    """
    curriculum = instance.curriculum
    program = instance.program
    if _find_in_programs([program], curriculum=curriculum):
        msg = 'Circular ref error. Program [{}] already contains Curriculum [{}]'.format(
            program,
            curriculum,
        )
        raise ValidationError(msg)


def _find_in_programs(programs, curriculum=None, program=None):
    """
    Travese the stucture of a given list of programs for a curriculm or program node.
    Returns True if an instance is found
    """
    if curriculum is None and program is None:
        raise TypeError('_find_in_programs takes at least one of (curriculum, program)')

    curricula = Curriculum.objects.filter(program__in=programs).prefetch_related('program_curriculum')

    if curriculum in curricula or program in programs:
        return True
    if not programs:
        return False

    child_programs = [program for curriculum in curricula for program in curriculum.program_curriculum.all()]
    return _find_in_programs(child_programs, curriculum=curriculum, program=program)


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
def ensure_external_key_uniquness__course_run(sender, instance, **kwargs):  # pylint: disable=unused-argument
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
        old_course_run = CourseRun.everything.get(pk=instance.pk)
        if instance.external_key == old_course_run.external_key and instance.course == old_course_run.course:
            return

    course = instance.course
    curricula = course.degree_course_curricula.select_related('program').all()
    if not curricula:
        check_course_runs_within_course_for_duplicate_external_key(course, instance)
    else:
        check_curricula_and_related_programs_for_duplicate_external_key(curricula, [instance])


@receiver(pre_save, sender=CurriculumCourseMembership)
def ensure_external_key_uniquness__curriculum_course_membership(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that if a curriculum_course_membership is created or modified, the
    external_keys for the course are unique within the linked curriculum/program
    """
    course_runs = instance.course.course_runs.filter(external_key__isnull=False)
    check_curricula_and_related_programs_for_duplicate_external_key([instance.curriculum], course_runs)


@receiver(pre_save, sender=Curriculum)
def ensure_external_key_uniquness__curriculum(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that if a curriculum is created or becomes associated with a different
    program, the curriculum's external_keys are/remain unique
    """
    if not instance.id:
        return  # If not instance.id, we can't access course_curriculum, so we can't do anything
    if instance.program:
        old_curriculum = Curriculum.objects.get(pk=instance.pk)
        if old_curriculum.program and instance.program.id == old_curriculum.program.id:
            return

    course_runs = CourseRun.objects.filter(
        course__degree_course_curricula=instance,
        external_key__isnull=False
    ).iterator()
    check_curricula_and_related_programs_for_duplicate_external_key([instance], course_runs)


def _build_external_key_sets(course_runs):
    """
    Helper function to extract two sets of ids from a list of course runs for use in filtering

    Parameters:
        - course runs: a collection of course runs
    Returns:
        - external_key_set: a set of all external_keys in `course_runs`
        - course_run_ids: a set of all ids in `course_runs`
    """
    external_key_set = set()
    course_run_ids = set()
    for course_run in course_runs:
        external_key_set.add(course_run.external_key)
        if course_run.id:
            course_run_ids.add(course_run.id)

    return external_key_set, course_run_ids


def _duplicate_external_key_message(course_runs):
    message = 'Duplicate external_key{} found: '.format('s' if len(course_runs) > 1 else '')
    for course_run in course_runs:
        message += ' [ external_key={} course_run={} course={} ]'.format(
            course_run.external_key,
            course_run,
            course_run.course
        )
    return message


def check_curricula_and_related_programs_for_duplicate_external_key(curricula, course_runs):
    """
    Helper function for verifying the uniqueness of external course keys within a collection
    of curricula.

    Parameters:
        - curricula: The curricula in which we are searching for duplicate external course keys
        - course runs: The course runs whose external course keys of which we are looking for duplicates

    Raises:
        If a course run is found under a curriculum in `curriculums` or under a program associated with
        a curriculum in `curricula`, a ValidationError is raised
    """
    external_key_set, course_run_ids = _build_external_key_sets(course_runs)
    programs = set()
    programless_curricula = set()
    for curriculum in curricula:
        if curriculum.program:
            programs.add(curriculum.program)
        else:
            programless_curricula.add(curriculum)

    # Get the first course run in the curricula or programs that have a duplicate external key
    # but aren't the course runs we're given
    course_runs = CourseRun.objects.filter(
        ~Q(id__in=course_run_ids),
        Q(external_key__in=external_key_set),
        (
            Q(course__degree_course_curricula__program__in=programs) |
            Q(course__degree_course_curricula__in=programless_curricula)
        ),
    ).select_related('course').distinct().all()
    if course_runs:
        message = _duplicate_external_key_message(course_runs)
        raise ValidationError(message)


def check_course_runs_within_course_for_duplicate_external_key(course, specific_course_run):
    """
    Helper function for verifying the uniqueness of external course keys within a course

    Parameters:
        - course: course in which we are searching for potential duplicate course keys
        - specific_course_run: The course run that we are looking for a duplicate of

    Raises:
        If a course run is found under `course` that has the same external
        course key as `specific_course_run` (but isn't `specific_course_run`),
        this function will raise a ValidationError
    """
    for course_run in course.course_runs.all():
        external_key = course_run.external_key
        if external_key == specific_course_run.external_key and course_run != specific_course_run:
            message = _duplicate_external_key_message([course_run])
            raise ValidationError(message)
