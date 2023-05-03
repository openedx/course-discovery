import logging

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import CourseRunType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Set 'is_marketable' to False for existing CourseRunType instances.
    ./manage.py change_is_marketable_to_false
    """
    help = 'Change status is_marketable in available types to False for existing CourseRunType instances.'

    def handle(self, *args, **options):
        self.change_is_marketable_in_course_run_type()

    def change_is_marketable_in_course_run_type(self):
        course_run_types = CourseRunType.objects.filter(is_marketable=True)
        for course_run_type in course_run_types:
            logger.info('Changed is_marketable status for CourseRunType: [%s] to False...', course_run_type.name)
            course_run_type.is_marketable = False
        CourseRunType.objects.bulk_update(course_run_types, ['is_marketable'])
