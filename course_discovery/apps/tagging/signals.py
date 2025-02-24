from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.emails import send_email_for_course_vertical_assignment


@receiver(post_save, sender=Course)
def notify_vertical_assignment(instance, created, **kwargs):
    """
    Sends email notifications to vertical managers when a new
    non-draft course entry is created.
    """
    if instance.draft or not created:
        return

    User = get_user_model()
    management_groups = getattr(settings, "VERTICALS_MANAGEMENT_GROUPS", [])

    recipients = list(
        User.objects.prefetch_related('groups').filter(groups__name__in=management_groups).distinct()
    )
    if recipients:
        send_email_for_course_vertical_assignment(instance, recipients)
