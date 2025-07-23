"""
Management command to send course deadline emails. This command is used to notify Project Coordinators (PCs) and Course
Editors about upcoming course deadlines, such as course run end dates. The command retrieves all
active course runs with self-paced pacing type and if the course run end date is within the specified deadline range
and there is no scheduled session, it sends an email to the course editors and PCs.
"""
import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import DurationField, ExpressionWrapper, F
from django.db.models.functions import Now, TruncDate
from django.utils.translation import gettext as _

from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.tasks import process_send_course_deadline_email
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.models import OrganizationUserRole

EMAIL_DELTA_DAYS = [2, 7, -1]
LAST_RUN_END_DELTA = -1

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send course deadline emails to Project Coordinators and Course Editors.'

    DEADLINE_VARIANTS = {
        2: "two_days_reminder",
        7: "seven_days_reminder",
        -1: "course_ended",
    }

    def handle(self, *args, **options):
        """
        Example usage: ./manage.py send_course_deadline_emails
        """
        logger.info("Initializing course deadline email management command.")
        now = datetime.now(timezone.utc)
        courses_with_deadlines = []
        courses_with_self_paced_runs = Course.objects.filter(
            course_runs__pacing_type=CourseRunPacing.Self,
            course_runs__end__isnull=False,
            product_source__slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG,
        ).annotate(
            days_until_end=ExpressionWrapper(
                TruncDate(F('course_runs__end')) - TruncDate(Now()),
                output_field=DurationField())
        ).filter(
            days_until_end__in=[timedelta(days=d) for d in EMAIL_DELTA_DAYS]
        ).prefetch_related(
            'course_runs',
            'editors',
        ).distinct()
        logger.info(f'Found {courses_with_self_paced_runs.count()} courses with self-paced runs.')
        courses_with_self_paced_runs = courses_with_self_paced_runs.iterator()

        for course in courses_with_self_paced_runs:
            advertised_run = course.advertised_course_run

            if advertised_run:
                if not course.course_runs.filter(status=CourseRunStatus.Reviewed).exists():
                    days_until_end = (advertised_run.end.date() - now.date()).days
                    if days_until_end in EMAIL_DELTA_DAYS:
                        self.handle_send_email_to_pcs_and_editors(
                            course, advertised_run, email_variant=self.DEADLINE_VARIANTS.get(days_until_end))
                        courses_with_deadlines.append(course)
                        logger.info(f'Deadline email has been scheduled for course {course.title} ({course.key}).')
                    else:
                        logger.info(f"Course {course.title} ({course.key}) has no advertised run "
                                    f"with end date within the specified range.")
                else:
                    logger.info(
                        f"Course {course.title} ({course.key}) has an active course run with status Scheduled."
                    )

            elif not advertised_run:
                last_course_run = course.course_runs.last()
                days_since_end = (last_course_run.end.date() - now.date()).days

                if days_since_end == LAST_RUN_END_DELTA:
                    self.handle_send_email_to_pcs_and_editors(
                        course, last_course_run, email_variant=self.DEADLINE_VARIANTS.get(days_since_end)
                    )
                    courses_with_deadlines.append(course)
                    logger.info(f'Deadline email has been scheduled for course {course.title} ({course.key}).')
                else:
                    logger.info(
                        f"Course '{course.title} ({course.key})' has no course run "
                        f"with end date within the specified range."
                    )

        self.log_courses_with_deadlines(courses_with_deadlines)

    def handle_send_email_to_pcs_and_editors(self, course, course_run, email_variant=None):
        """
        Schedule the sending of course deadline emails to Project Coordinators and Course Editors.
        This method retrieves the email addresses of course editors and project coordinators associated with the course
        and schedules the email to be sent using the `process_send_course_deadline_email` task.
        """
        course_editors = list(course.draft_version.editors.values_list('user__email', flat=True).distinct())
        project_coordinators = list(OrganizationUserRole.objects.filter(
            organization__in=course.authoring_organizations.all(),
            role=InternalUserRole.ProjectCoordinator
        ).values_list('user__email', flat=True).distinct())
        recipients = list(set(course_editors + project_coordinators))

        logger.info(f"Scheduling deadline email for course {course.title} ({course.key}).")
        process_send_course_deadline_email.apply_async(
            args=[course.key, course_run.key, recipients, email_variant],
        )

    def log_courses_with_deadlines(self, courses):
        """
        Log the courses for which deadline emails have been scheduled.
        """
        if courses:
            titles = "\n".join([f"- {course.title} ({course.uuid})" for course in courses])
            logger.info(f"Scheduled course deadline emails for:\n{titles}")
        else:
            logger.info('No courses with deadline within the specified range were found.')
