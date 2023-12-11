import re

from django.contrib.auth.models import Permission
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from slugify import slugify

from course_discovery.apps.course_metadata.constants import SUBDIRECTORY_PROGRAM_SLUG_FORMAT_REGEX as slug_format
from course_discovery.apps.course_metadata.models import Program, slugify_with_slashes
from course_discovery.apps.publisher.models import OrganizationExtension


@receiver(post_save, sender=OrganizationExtension)
def add_permissions_to_organization_group(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    if created:
        target_permissions = Permission.objects.filter(
            codename__in=['add_person', 'change_person', 'delete_person']
        )
        instance.group.permissions.add(*target_permissions)


@receiver(m2m_changed, sender=Program.authoring_organizations.through)
def autogenerate_program_slug(sender, instance, *args, **kwargs):  # pylint: disable=unused-argument
    if instance.authoring_organizations.count() > 0 and not bool(re.fullmatch(slug_format, instance.marketing_slug)):
        category_map = {
            'micromasters': 'masters',
            'microbachelors': 'bachelors',
            'professional-certificate': 'certificates'
        }
        org_name = instance.authoring_organizations.first().slug
        program_title = instance.title
        category_type = instance.type.slug

        if category_type == 'xseries':
            slug_head = category_type
        elif category_type == 'license':
            slug_head = 'certificates'
        else:
            slug_head = f'{category_map[category_type]}/{category_type}' if category_map.get(category_type) \
                else f'{category_type}'

        instance.marketing_slug = slugify_with_slashes(f'{slug_head}/{org_name}-{slugify(program_title)}')
        instance.save()
