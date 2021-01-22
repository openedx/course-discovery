from django.contrib.auth.models import Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

from course_discovery.apps.publisher.models import OrganizationExtension


@receiver(post_save, sender=OrganizationExtension)
def add_permissions_to_organization_group(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    if created:
        target_permissions = Permission.objects.filter(
            codename__in=['add_person', 'change_person', 'delete_person']
        )
        instance.group.permissions.add(*target_permissions)
