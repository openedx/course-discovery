"""
Management command to send course deadline emails. This command is used to notify Project Coordinators (PCs) and Course Editors about upcoming course deadlines,
such as course run end dates. The command retrieves all active course runs with self-paced pacing type and if the course run end date is within the specified deadline range and there is no scheduled session,
it sends an email to the course editors and PCs.
"""
import logging
from datetime import datetime, timezone, timedelta

from django.core.management import BaseCommand, CommandError
from django.utils.translation import gettext as _

from course_discovery.apps.course_metadata.choices import CourseRunStatus, CourseRunPacing
from course_discovery.apps.course_metadata.models import CourseRun, Course
from course_discovery.apps.publisher.models import OrganizationUserRole
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.course_metadata.tasks import process_send_course_deadline_email


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send course deadline emails to Project Coordinators and Course Editors.'

    def handle(self, *args, **options):
        logger.info("Initalizing course deadline email management command.")
        courses_with_self_paced_runs = Course.objects.filter(
            course_runs__pacing_type=CourseRunPacing.Self,
            course_runs__status=CourseRunStatus.Published,
            product_source__slug='edx',
        ).distinct()
        logger.info(f'Found {courses_with_self_paced_runs.count()} courses with self-paced runs.')
        courses_with_self_paced_runs = courses_with_self_paced_runs.iterator()
        for course in courses_with_self_paced_runs:
            advertised_run = course.advertised_course_run
            import pdb; pdb.set_trace();
            if advertised_run and advertised_run.end:
                delta = advertised_run.end - datetime.now(timezone.utc)
                if delta.days in [2, 7]:
                    active_runs = course.active_course_runs.all()
                    if not active_runs.filter(status=CourseRunStatus.Scheduled).exists():
                        self.handle_send_email_to_pcs_and_editors(course, email_variant=delta.days)
                    else:
                        logger.info(f'Course {course.title} ({course.key}) has an active course run with status Scheduled.')
                else:
                    logger.info(f'Course {course.title} ({course.key}) has no advertised course run or the end date is not within the specified range.')
                pass

    def handle_send_email_to_pcs_and_editors(self, course, email_variant=None):
        course_editors = course.editors.values_list('email', flat=True).distinct()
        pcs = OrganizationUserRole.objects.filter(
            organization__in=course.authoring_organizations.all(),
            role=InternalUserRole.ProjectCoordinator
        ).values_list('user__email', flat=True).distinct()
        recipients = {
            'course_editors': course_editors,
            'project_coordinators': pcs,
        }

        process_send_course_deadline_email.apply_async(
            args=[course, recipients, email_variant],
        )
