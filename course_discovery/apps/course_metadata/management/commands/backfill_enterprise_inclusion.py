from django.core.management.base import BaseCommand

from course_discovery.apps.course_metadata.management.commands.constants import course_keys, org_uuids
from course_discovery.apps.course_metadata.models import Course, Organization


class Command(BaseCommand):
    """
    Management command for assigning enterprise_learner roles to existing enterprise users.
    Example usage:
      $ ./manage.py backfill_enterprise_inclusion
    """
    help = 'Populates new enterprise_subscription_inclusion boolean with existing data.'

    def handle(self, *args, **options):
        for org_uuid in org_uuids:
            org = Organization.objects.filter(uuid=org_uuid).first()
            org.enterprise_subscription_inclusion = True
            org.save()
        for course_key in course_keys:
            course = Course.objects.filter(key=course_key).first()
            course.enterprise_subscription_inclusion = True
            course.save()
