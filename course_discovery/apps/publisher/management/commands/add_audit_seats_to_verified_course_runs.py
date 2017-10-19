import logging

from django.core.management import BaseCommand

from course_discovery.apps.publisher.models import CourseRun, Seat

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Adds audit seats to credit/verified course runs'

    def add_arguments(self, parser):
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Commit the new seats to the database')

    def handle(self, *args, **options):
        course_runs = CourseRun.objects.filter(seats__type__in=(Seat.CREDIT, Seat.VERIFIED,)).exclude(
            seats__type=Seat.AUDIT)
        if options['commit']:
            for course_run in course_runs:
                seat = course_run.seats.create(type=Seat.AUDIT, price=0, upgrade_deadline=None)
                course_run_id = course_run.lms_course_id or course_run.id
                logger.info('Created audit seat [%d] for course run [%s]', seat.id, course_run_id)
        else:
            logger.info('The following [%d] course runs lack audit seats...', course_runs.count())
            for course_run in course_runs:
                logger.info('\t%s', course_run.lms_course_id or course_run.id)
