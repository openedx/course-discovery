import logging

from django.core.management.base import BaseCommand

from course_discovery.apps.course_metadata.management.commands.constants import course_keys, org_uuids
from course_discovery.apps.course_metadata.models import Course, Organization

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for assigning enterprise_learner roles to existing enterprise users.
    Example usage:
      $ ./manage.py backfill_enterprise_inclusion
    """
    help = 'Populates new enterprise_subscription_inclusion boolean with existing data.'

    def handle(self, *args, **options):
        for org_uuid in org_uuids:
            try:
                org = Organization.objects.get(uuid=org_uuid)
                org.enterprise_subscription_inclusion = True
                org.save()
            except Organization.DoesNotExist:
                logger.info('Organization with uuid %s not found. Skipping.', org_uuid)
        for course_key in course_keys:
            try:
                course = Course.objects.get(key=course_key)
                course.enterprise_subscription_inclusion = True
                course.save()
            except Course.DoesNotExist:
                logger.info('Course with course key %s not found. Skipping.', course_key)
