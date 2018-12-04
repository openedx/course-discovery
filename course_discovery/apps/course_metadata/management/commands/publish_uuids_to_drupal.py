import logging

from django.core.management import BaseCommand
from course_discovery.apps.course_metadata.models import CourseRun, DrupalPublishUuidConfig
from course_discovery.apps.course_metadata.publishers import CourseRunMarketingSitePublisher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Based on the configuration object, publishes out the UUID'

    def handle(self, *args, **options):
        config = DrupalPublishUuidConfig.get_solo()
        course_run_ids = config.course_run_ids.split(',')
        course_runs = CourseRun.objects.filter(key__in=course_run_ids)

        for course_run in course_runs:
            publisher = CourseRunMarketingSitePublisher(course_run.course.partner)
            publisher.publish_obj(course_run)
