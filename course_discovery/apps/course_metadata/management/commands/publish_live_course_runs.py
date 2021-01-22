import datetime
import logging

import pytz
from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Based on course run go_live dates, publish any runs that are due'

    def handle(self, *args, **options):
        failed = False
        now = datetime.datetime.now(pytz.UTC)
        course_runs = CourseRun.objects.filter(status=CourseRunStatus.Reviewed, go_live_date__lte=now)

        for course_run in course_runs:
            logger.info(_('Publishing course run {key}').format(key=course_run.key))

            try:
                course_run.publish()
            except Exception:  # pylint: disable=broad-except
                logger.exception(_('Failed to publish {key}').format(key=course_run.key))
                failed = True
            else:
                logger.info(_('Successfully published {key}').format(key=course_run.key))

        if failed:
            raise CommandError(_('One or more course runs failed to publish.'))
