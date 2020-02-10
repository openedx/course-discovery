import logging

import waffle
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.constants import MASTERS_PROGRAM_TYPE_SLUG
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Curriculum, CurriculumCourseMembership, CurriculumProgramMembership, Organization, Program
)
from course_discovery.apps.course_metadata.publishers import ProgramMarketingSitePublisher
from course_discovery.apps.course_metadata.salesforce import (
    populate_official_with_existing_draft, requires_salesforce_update
)
from course_discovery.apps.course_metadata.utils import get_salesforce_util

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


@receiver(pre_save, sender=Curriculum)
def check_curriculum_for_cycles(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Check for circular references in program structure before saving.
    Short circuits on:
        - newly created Curriculum since it cannot have member programs yet
        - Curriculum with a 'None' program since there cannot be a loop
    """
    curriculum = instance
    if not curriculum.id or not curriculum.program:
        return

    if _find_in_programs(curriculum.program_curriculum.all(), target_program=curriculum.program):
        raise ValidationError('Circular ref error.  Curriculum already contains program {}'.format(curriculum.program))


@receiver(pre_save, sender=CurriculumProgramMembership)
def check_curriculum_program_membership_for_cycles(sender, instance, **kwargs):
    """
    Check for circular references in program structure before saving.
    """
    curriculum = instance.curriculum
    program = instance.program
    if _find_in_programs([program], target_curriculum=curriculum):
        msg = 'Circular ref error. Program [{}] already contains Curriculum [{}]'.format(
            program,
            curriculum,
        )
        raise ValidationError(msg)


def _find_in_programs(existing_programs, target_curriculum=None, target_program=None):
    """
    Travese the stucture of a given list of programs for a target curriculm or program node.
    Returns True if an instance is found
    """
    if target_curriculum is None and target_program is None:
        raise TypeError('_find_in_programs takes at least one of (target_curriculum, target_program)')

    if not existing_programs:
        return False
    if target_program in existing_programs:
        return True

    curricula = Curriculum.objects.filter(program__in=existing_programs).prefetch_related('program_curriculum')
    if target_curriculum in curricula:
        return True

    child_programs = [program for curriculum in curricula for program in curriculum.program_curriculum.all()]
    return _find_in_programs(child_programs, target_curriculum=target_curriculum, target_program=target_program)


# Invalidate API cache when any model in the course_metadata app is saved or
# deleted. Given how interconnected our data is and how infrequently our models
# change (data loading aside), this is a clean and simple way to ensure correctness
# of the API while providing closer-to-optimal cache TTLs.
for model in apps.get_app_config('course_metadata').get_models():
    for signal in (post_save, post_delete):
        signal.connect(api_change_receiver, sender=model)


@receiver(pre_save, sender=CourseRun)
def ensure_external_key_uniqueness__course_run(sender, instance, **kwargs):  # pylint: disable=unused-argument
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
    # This is for the intermediate time between the official course run being created through
    # utils.py set_official_state and before the Course reference is updated to the official course.
    # See course_metadata/models.py under the CourseRun model inside of the update_or_create_official_version
    # function for when the official run is created and when several lines later, the official course
    # is added to it.
    if not instance.draft and instance.course.draft:
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
def ensure_external_key_uniqueness__curriculum_course_membership(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Pre-save hook to validate that if a curriculum_course_membership is created or modified, the
    external_keys for the course are unique within the linked curriculum/program
    """
    course_runs = instance.course.course_runs.filter(external_key__isnull=False)
    check_curricula_and_related_programs_for_duplicate_external_key([instance.curriculum], course_runs)


@receiver(pre_save, sender=Curriculum)
def ensure_external_key_uniqueness__curriculum(sender, instance, **kwargs):  # pylint: disable=unused-argument
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


@receiver(post_save, sender=Organization)
def update_or_create_salesforce_organization(instance, created, **kwargs):  # pylint: disable=unused-argument
    partner = instance.partner
    util = get_salesforce_util(partner)
    if util:
        if not instance.salesforce_id:
            util.create_publisher_organization(instance)
        if not created and requires_salesforce_update('organization', instance):
            util.update_publisher_organization(instance)


@receiver(post_save, sender=Course)
def update_or_create_salesforce_course(instance, created, **kwargs):  # pylint: disable=unused-argument
    partner = instance.partner
    util = get_salesforce_util(partner)
    # Only bother to create the course if there's a util, and the auth orgs are already set up
    if util and instance.authoring_organizations.first():
        if not created and not instance.draft:
            created_in_salesforce = False
            # Only populate the Official instance if the draft information is ready to go (has auth orgs set)
            if (not instance.salesforce_id and
                    instance.draft_version and
                    instance.draft_version.authoring_organizations.first()):
                created_in_salesforce = populate_official_with_existing_draft(instance, util)
            if not created_in_salesforce and requires_salesforce_update('course', instance):
                util.update_course(instance)


@receiver(m2m_changed, sender=Course.authoring_organizations.through)
def authoring_organizations_changed(sender, instance, action, **kwargs):  # pylint: disable=unused-argument
    # Only do this after an auth org has been added, the salesforce_id isn't set and it's a draft (new)
    if action == 'post_add' and not instance.salesforce_id and instance.draft:
        partner = instance.partner
        util = get_salesforce_util(partner)
        if util:
            util.create_course(instance)


@receiver(post_save, sender=CourseRun)
def update_or_create_salesforce_course_run(instance, created, **kwargs):  # pylint: disable=unused-argument
    try:
        partner = instance.course.partner
    except (Course.DoesNotExist, Partner.DoesNotExist):
        # exit early in the unusual event that we can't look up the appropriate partner
        return
    util = get_salesforce_util(partner)
    if util:
        if instance.draft:
            util.create_course_run(instance)
        elif not created and not instance.draft:
            created_in_salesforce = False
            if not instance.salesforce_id and instance.draft_version:
                created_in_salesforce = populate_official_with_existing_draft(instance, util)
            if not created_in_salesforce and requires_salesforce_update('course_run', instance):
                util.update_course_run(instance)


def _build_external_key_sets(course_runs):
    """
    Helper function to extract two sets of ids from a list of course runs for use in filtering
    However, the external_keys with null or empty string values are not included in the
    returned external_key_set.

    Parameters:
        - course runs: a collection of course runs
    Returns:
        - external_key_set: a set of all external_keys in `course_runs`
        - course_run_ids: a set of all ids in `course_runs`
    """
    external_key_set = set()
    course_run_ids = set()
    for course_run in course_runs:
        if course_run.external_key:
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
