"""
Celery tasks for course metadata.
"""
import logging

from celery import shared_task

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import BulkOperationStatus, BulkOperationType
from course_discovery.apps.course_metadata.data_loaders.course_loader import CourseLoader
from course_discovery.apps.course_metadata.models import BulkOperationTask, Course, CourseType, Program, ProgramType

LOGGER = logging.getLogger(__name__)


@shared_task()
def update_org_program_and_courses_ent_sub_inclusion(org_pk, org_sub_inclusion):
    """
    Task to update an organization's child courses' and programs' enterprise subscription inclusion status upon saving
    the org object.
    Arguments:
        org_pk (int): primary key of the organization
        org_sub_inclusion (bool): whether or not the org is included in enterprise subscriptions
    """
    courses = Course.everything.filter(
        authoring_organizations__pk=org_pk,
        enterprise_subscription_inclusion__in=[None, True],
        type__slug__in=[
            CourseType.AUDIT,
            CourseType.VERIFIED_AUDIT,
            CourseType.PROFESSIONAL,
            CourseType.CREDIT_VERIFIED_AUDIT,
            CourseType.EMPTY
        ]
    )
    sub_tag_log = "Org: %s has been saved. Updating enterprise sub tagging logic for %s %s"
    LOGGER.info(sub_tag_log, org_pk, len(courses), 'courses')
    course_ids = []
    for course in courses:
        course.enterprise_subscription_inclusion = org_sub_inclusion
        course.save()
        course_ids.append(course.id)
    programs = Program.objects.filter(
        courses__in=course_ids,
        type__slug__in=[
            ProgramType.XSERIES,
            ProgramType.MICROMASTERS,
            ProgramType.PROFESSIONAL_CERTIFICATE,
            ProgramType.PROFESSIONAL_PROGRAM_WL,
            ProgramType.MICROBACHELORS
        ]
    )
    LOGGER.info(sub_tag_log, org_pk, len(programs), 'programs')
    for program in programs:
        program.save()


def select_and_init_bulk_operation_loader(bulk_operation_task):
    """
    Identifies and instantiates the appropriate data loader for a given BulkOperationTask.
    """
    if bulk_operation_task.task_type == BulkOperationType.CourseCreate:
        partner = Partner.objects.get(short_code='edx')
        loader = CourseLoader(
            partner,
            csv_file=bulk_operation_task.csv_file,
            product_source='edx',
            task_type=BulkOperationType.CourseCreate,
        )
        return loader
    else:
        raise ValueError(f"Cannot find loader for task type {bulk_operation_task.task_type}")


@shared_task()
def process_bulk_operation(bulk_operation_task_id):
    """
    Task to process a given BulkOperationTask.
    """
    LOGGER.info(f"Starting processing for BulkOperationTask {bulk_operation_task_id}")
    try:
        bulk_operation_task = BulkOperationTask.objects.get(id=bulk_operation_task_id)
        loader = select_and_init_bulk_operation_loader(bulk_operation_task)
        bulk_operation_task.status = BulkOperationStatus.Processing
        bulk_operation_task.save()

        summary = loader.ingest()
        bulk_operation_task.task_summary = summary
        bulk_operation_task.status = BulkOperationStatus.Completed
        bulk_operation_task.save()
    except Exception as exc:
        LOGGER.exception(f"An exception occurred while processing BulkOperationTask with id {bulk_operation_task_id}")
        bulk_operation_task.status = BulkOperationStatus.Failed
        bulk_operation_task.save()
        raise exc
