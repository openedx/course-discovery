import logging
import time
from datetime import datetime, timezone

import waffle  # lint-amnesty, pylint: disable=invalid-django-waffle-import
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from openedx_events.content_authoring.data import CourseCatalogData
from openedx_events.content_authoring.signals import COURSE_CATALOG_INFO_CHANGED

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.constants import MASTERS_PROGRAM_TYPE_SLUG
from course_discovery.apps.course_metadata.data_loaders.api import CoursesApiDataLoader
from course_discovery.apps.course_metadata.models import (
    AdditionalMetadata, CertificateInfo, Course, CourseEditor, CourseEntitlement, CourseLocationRestriction, CourseRun,
    Curriculum, CurriculumCourseMembership, CurriculumProgramMembership, Fact, GeoLocation, Organization, ProductMeta,
    ProductValue, Program, Seat
)
from course_discovery.apps.course_metadata.publishers import ProgramMarketingSitePublisher
from course_discovery.apps.course_metadata.salesforce import (
    populate_official_with_existing_draft, requires_salesforce_update
)
from course_discovery.apps.course_metadata.tasks import update_org_program_and_courses_ent_sub_inclusion
from course_discovery.apps.course_metadata.utils import data_modified_timestamp_update, get_salesforce_util

logger = logging.getLogger(__name__)
User = get_user_model()


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
        raise ValidationError(f'Circular ref error.  Curriculum already contains program {curriculum.program}')


@receiver(pre_save, sender=CurriculumProgramMembership)
def check_curriculum_program_membership_for_cycles(sender, instance, **kwargs):  # pylint: disable=unused-argument
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


def connect_api_change_receiver():
    """
    Invalidate API cache when any model in the course_metadata app is saved or
    deleted. Given how interconnected our data is and how infrequently our models
    change (data loading aside), this is a clean and simple way to ensure correctness
    of the API while providing closer-to-optimal cache TTLs.
    """
    for model in apps.get_app_config('course_metadata').get_models():
        for signal in (post_save, post_delete):
            signal.connect(api_change_receiver, sender=model)


connect_api_change_receiver()


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
def update_or_create_salesforce_organization(instance, created, **kwargs):
    partner = instance.partner
    util = get_salesforce_util(partner)
    if util:
        if not instance.salesforce_id:
            util.create_publisher_organization(instance)
        if not created and requires_salesforce_update('organization', instance):
            util.update_publisher_organization(instance)


@shared_task
@receiver(post_save, sender=Organization)
def update_enterprise_inclusion_for_courses_and_programs(instance, created, **kwargs):  # pylint: disable=unused-argument
    update_org_program_and_courses_ent_sub_inclusion.delay(
        org_pk=instance.pk, org_sub_inclusion=instance.enterprise_subscription_inclusion
    )


@receiver(post_save, sender=Course)
def update_or_create_salesforce_course(instance, created, **kwargs):
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
def update_or_create_salesforce_course_run(instance, created, **kwargs):
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


@receiver(COURSE_CATALOG_INFO_CHANGED)
def update_course_data_from_event(**kwargs):
    """
    When we get a signal indicating that the course catalog was updated, make sure to update the
    data on course-discovery, too.

    Args:
        kwargs: event data sent to signal
    """
    course_data = kwargs.get('catalog_info', None)
    if not course_data or not isinstance(course_data, CourseCatalogData):
        logger.error('Received null or incorrect data from COURSE_CATALOG_INFO_CHANGED.')
        return

    event_metadata = kwargs.get('metadata')
    if event_metadata:
        event_timestamp = event_metadata.time
        time_diff = datetime.now(tz=timezone.utc) - event_timestamp
        if time_diff.seconds < settings.EVENT_BUS_MESSAGE_DELAY_THRESHOLD_SECONDS:
            logger.debug(f"COURSE_CATALOG_INFO_CHANGED event received within the delay "
                         f"applicable window for course run {course_data.course_key}.")
            time.sleep(settings.EVENT_BUS_PROCESSING_DELAY_SECONDS)

    # Handle optional fields.
    schedule_data = course_data.schedule_data
    end = str(schedule_data.end) if schedule_data.end else None
    enrollment_end = str(schedule_data.enrollment_end) if schedule_data.enrollment_end else None
    enrollment_start = str(schedule_data.enrollment_start) if schedule_data.enrollment_start else None
    body = {
        'id': str(course_data.course_key),
        'start': str(course_data.schedule_data.start),
        'end': end,
        'name': course_data.name,
        'enrollment_start': enrollment_start,
        'enrollment_end': enrollment_end,
        'hidden': course_data.hidden,
        'license': '',  # license cannot be None
        'pacing': course_data.schedule_data.pacing,
    }

    # Currently, we are not passing along partner information as part of the event.
    # Because of this, we are assuming that all events are going to the default id for now.
    partner = Partner.objects.get(id=settings.DEFAULT_PARTNER_ID)
    data_loader = CoursesApiDataLoader(partner, enable_api=False)
    data_loader.process_single_course_run(body)


@receiver(m2m_changed, sender=Course.collaborators.through)
def course_collaborators_changed(sender, instance, action, **kwargs):  # pylint: disable=unused-argument
    """
    If the course's collaborators have been changed, update the data modified timestamp for related Course obj.

    Collaborator is a sorted m2m field. The field internally clears all the value whenever the course is saved & re-adds
    all the values, regardless of any change. This is done because the field needs to maintain the order.
    To determine if the course collaborators have been changed, get the collab pk from non-draft/official version,
    compare that set with values coming in from m2m_relation's pre_add or pre_remove, and if the set is not the same,
    then the collaborators have been changed.
    https://github.com/jazzband/django-sortedm2m/blob/e646aafa81416c7888a7d358c7293bd4f707a25f/sortedm2m/fields.py#L47-L50
    """
    if action in ['pre_add', 'pre_remove'] and instance.draft and instance.official_version and not kwargs['reverse']:
        official_version_collaborators_pk = set(
            instance.official_version.collaborators.all().values_list('pk', flat=True)
        )
        if official_version_collaborators_pk != kwargs['pk_set']:
            logger.info(f"Collaborator M2M relation has been updated for course {instance.key}.")
            instance.set_data_modified_timestamp()


@receiver(m2m_changed, sender=Course.subjects.through)
def course_subjects_changed(sender, instance, action, **kwargs):  # pylint: disable=unused-argument
    """
    If the course's subjects have been changed, update the data modified timestamp for related Course obj.

    Subjects is a sorted m2m field. The field internally clears all the value whenever the course is saved & re-adds
    all the values, regardless of any change. This is done because the field needs to maintain the order.
    To determine if the course subjects have been changed, get the subjects pk from non-draft/official version,
    compare that set with values coming in from m2m_relation's pre_add or pre_remove, and if the set is not the same,
    then the subjects have been changed.
    https://github.com/jazzband/django-sortedm2m/blob/e646aafa81416c7888a7d358c7293bd4f707a25f/sortedm2m/fields.py#L47-L50
    """
    if action in ['pre_add', 'pre_remove'] and instance.draft and instance.official_version and not kwargs['reverse']:
        official_version_subjects_pk = set(
            instance.official_version.subjects.all().values_list('pk', flat=True)
        )
        if official_version_subjects_pk != kwargs['pk_set']:
            logger.info(f"Subject M2M relation has been updated for course {instance.key}.")
            instance.set_data_modified_timestamp()


@receiver(m2m_changed, sender=ProductMeta.keywords.through)
def product_meta_taggable_changed(sender, instance, action, **kwargs):
    """
    Signal handler to handle Taggable manager changes for the keywords field on ProductMeta model.
    """
    if action in ['pre_add', 'pre_remove'] and not kwargs['reverse'] \
            and kwargs['pk_set'] and instance._meta.label == 'course_metadata.ProductMeta':
        logger.info(f"{sender} has been updated for ProductMeta {instance.pk}.")
        instance.update_product_data_modified_timestamp(bypass_has_changed=True)


@receiver(m2m_changed, sender=Course.topics.through)
def course_topics_taggable_changed(sender, instance, action, **kwargs):
    """
    Signal handler to handle Taggable manager changes for the course tag field or course related models' tag fields.
    """
    if action in ['pre_add', 'pre_remove'] and not kwargs['reverse'] \
            and kwargs['pk_set'] and instance._meta.label == 'course_metadata.Course' and instance.draft:
        logger.info(f"{sender} has been updated for Course {instance.key}.")
        instance.set_data_modified_timestamp()


@receiver(m2m_changed, sender=AdditionalMetadata.facts.through)
def additional_metadata_facts_changed(sender, instance, action, **kwargs):
    """
    Signal handler to update data modified timestamp for related Courses when fact objects are
    added to AdditionalMetadata instance.
    """
    if action == 'pre_add' and not kwargs['reverse']:
        logger.info(f"{sender} has been updated for AdditionalMetadata {instance.pk}.")
        instance.update_product_data_modified_timestamp(bypass_has_changed=True)


@receiver(m2m_changed, sender=CourseRun.transcript_languages.through)
def course_run_transcript_languages_changed(sender, instance, action, **kwargs):
    """
    If the course run's transcript languages m2m field has been changed, update the data modified timestamp for
    related Course obj.
    """
    if action in ['pre_add', 'pre_remove'] and not kwargs['reverse'] and instance.draft:
        logger.info(f"{sender} has been updated for course run {instance.key}.")
        instance.course.set_data_modified_timestamp()


@receiver(m2m_changed, sender=CourseRun.staff.through)
def course_run_staff_changed(sender, instance, action, **kwargs):  # pylint: disable=unused-argument
    """
    If the course run staff m2m field has been changed, update the data modified timestamp for
    related Course obj.

    Staff is a sorted m2m field. The field internally clears all the value whenever the course run is saved & re-adds
    all the values, regardless of any change. This is done because the field needs to maintain the order.
    To determine if the course run staff has been changed, get the staff pk from non-draft/official version,
    compare that set with values coming in from m2m_relation's pre_add or pre_remove, and if the set is not the same,
    then the staff has been changed.
    https://github.com/jazzband/django-sortedm2m/blob/e646aafa81416c7888a7d358c7293bd4f707a25f/sortedm2m/fields.py#L47-L50
    """
    if action in ['pre_add', 'pre_remove'] and instance.draft and instance.official_version and not kwargs['reverse']:
        official_version_staff_pk = set(
            instance.official_version.staff.all().values_list('pk', flat=True)
        )
        if official_version_staff_pk != kwargs['pk_set']:
            logger.info(f"Staff M2M relation has been updated for course run {instance.key}.")
            instance.course.set_data_modified_timestamp()


def connect_course_data_modified_timestamp_related_models():
    """
    This wrapper is used to connect Course model's related models (ForeignKey)
    whose data change should update data_modified_timestamp in Course model.
    """
    for model in [
        AdditionalMetadata,
        CertificateInfo,
        CourseRun,
        CourseLocationRestriction,
        CourseEntitlement,
        GeoLocation,
        ProductMeta,
        ProductValue,
        Seat,
        Fact,
    ]:
        pre_save.connect(data_modified_timestamp_update, sender=model)


def disconnect_course_data_modified_timestamp_related_models():
    """
    This wrapper is used to disconnect Course model's related models (ForeignKey)
    whose data change should update data_modified_timestamp in Course model. This
    is to be used in unit tests to disconnect these signals.
    """
    for model in [
        AdditionalMetadata,
        CertificateInfo,
        CourseRun,
        CourseLocationRestriction,
        CourseEntitlement,
        GeoLocation,
        ProductMeta,
        ProductValue,
        Seat,
        Fact
    ]:
        pre_save.disconnect(data_modified_timestamp_update, sender=model)


def disconnect_course_data_modified_timestamp_signal_handlers():
    """
    Util method to disconnect all signal handlers that update data_modified_timestamp on
    Course model.
    """
    disconnect_course_data_modified_timestamp_related_models()
    m2m_changed.disconnect(product_meta_taggable_changed, sender=ProductMeta.keywords.through)
    m2m_changed.disconnect(course_topics_taggable_changed, sender=Course.topics.through)
    m2m_changed.disconnect(additional_metadata_facts_changed, sender=AdditionalMetadata.facts.through)
    m2m_changed.disconnect(course_run_transcript_languages_changed, sender=CourseRun.transcript_languages.through)
    m2m_changed.disconnect(course_collaborators_changed, Course.collaborators.through)
    m2m_changed.disconnect(course_subjects_changed, Course.subjects.through)
    m2m_changed.disconnect(course_run_staff_changed, CourseRun.staff.through)


def connect_course_data_modified_timestamp_signal_handlers():
    """
    Util method to connect all signal handlers that update data_modified_timestamp on
    Course model.
    """
    connect_course_data_modified_timestamp_related_models()
    m2m_changed.connect(product_meta_taggable_changed, sender=ProductMeta.keywords.through)
    m2m_changed.connect(course_topics_taggable_changed, sender=Course.topics.through)
    m2m_changed.connect(additional_metadata_facts_changed, sender=AdditionalMetadata.facts.through)
    m2m_changed.connect(course_run_transcript_languages_changed, sender=CourseRun.transcript_languages.through)
    m2m_changed.connect(course_collaborators_changed, Course.collaborators.through)
    m2m_changed.connect(course_subjects_changed, Course.subjects.through)
    m2m_changed.connect(course_run_staff_changed, CourseRun.staff.through)


@receiver(m2m_changed, sender=User.groups.through)
def handle_organization_group_removal(sender, instance, action, pk_set, reverse, **kwargs):  # pylint: disable=unused-argument
    """
    When a user is removed from a group, ensure that they are also removed
    from the course editor roles for any organizations linked to the group
    """

    if (action != 'pre_remove') or reverse:
        return

    course_editor_objects = (
        CourseEditor.objects.filter(user=instance)
        .select_related('course')
        .prefetch_related('course__authoring_organizations')
    )
    user_org_ids = (
        instance.groups.exclude(id__in=pk_set)
        .prefetch_related('organization_extension')
        .values_list('organization_extension__organization', flat=True)
    )
    # Remove the None values occuring due to some groups not having any associated organization_extension
    user_org_ids = [pk for pk in user_org_ids if pk is not None]

    # In the loop below, for every course editor instance associated to the user,
    # we calculate the course's authoring organizations and verify if the user
    # is a part of at least one of those. If not, we remove the course editor instance
    for course_editor_instance in course_editor_objects:
        course_authoring_org_ids = {org.id for org in course_editor_instance.course.authoring_organizations.all()}
        if not course_authoring_org_ids.intersection(user_org_ids):
            course_editor_instance.delete()
            logger.info(
                f"User {instance.username} no longer holds editor privileges "
                f"for course {course_editor_instance.course.title}"
            )


connect_course_data_modified_timestamp_related_models()
