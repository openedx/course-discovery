import logging

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.utils import get_salesforce_util

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Updates course runs data in salesforce '

    def handle(self, *args, **options):
        failed_course_runs = []
        partners = Partner.objects.all()
        for partner in partners:
            util = get_salesforce_util(partner)
            if util:
                course_runs = CourseRun.objects.filter(draft=False, course__partner=partner).\
                    exclude(salesforce_id__isnull=True)
                for course_run in course_runs:
                    try:
                        util.update_course_run(course_run)
                        logger.info('Successfully synced the salesforce {key}'.format(key=course_run.key))
                    except Exception:  # pylint: disable=broad-except
                        failed_course_runs.append(course_run.key)

        if failed_course_runs:
            raise CommandError('Following course runs were unable to sync with salesforce  {}'.format(
                failed_course_runs))
