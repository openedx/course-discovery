import logging

from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.exceptions import UnpublishError
from course_discovery.apps.course_metadata.models import CourseRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Unpublishes marketing site URLs from any old inactive course runs to newer active runs'

    def handle(self, *args, **options):
        success = True

        # Since we know we will call unpublish_inactive_runs for nearly every single course in our catalog, let's
        # try to optimize a little bit by only making one database query. We ask for all course runs, sort by course,
        # then hand the set of published course runs into unpublish_inactive_runs.
        published_runs = CourseRun.objects.filter(status=CourseRunStatus.Published).order_by('course').iterator()

        current_course = None
        current_runs = set()

        # Iterate through all published runs, gather up all the runs for a given course, group them, and
        # send them to unpublish_inactive_runs.
        for run in published_runs:
            if current_course and current_course != run.course:
                success = self.update_course(current_course, current_runs) and success
                current_runs = set()

            current_course = run.course
            current_runs.add(run)

        # and handle the last group of runs too
        if current_runs:
            success = self.update_course(current_course, current_runs) and success

        if not success:
            raise CommandError(_('One or more courses failed to unpublish.'))

    @staticmethod
    def update_course(course, runs):
        try:
            if course.unpublish_inactive_runs(published_runs=runs):
                logger.info(_('Successfully unpublished runs in course {key}').format(key=course.key))
            return True
        except UnpublishError:
            logger.exception(_('Failed to unpublish runs in course {key}').format(key=course.key))
            return False
