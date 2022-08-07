"""
Celery tasks for course metadata.
"""
import logging

from celery import shared_task

from course_discovery.apps.course_metadata.models import Course, CourseType, Program, ProgramType

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
    courses = Course.objects.filter(
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
    for program in programs:
        program.save()
