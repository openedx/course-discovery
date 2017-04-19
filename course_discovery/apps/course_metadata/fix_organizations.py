import logging
from itertools import groupby

from django.db import transaction

from course_discovery.apps.course_metadata.models import Organization, Course, Position, Program

logger = logging.getLogger(__name__)

# 1. Sort by key as a prerequisite to groupby.
# 2. Sort by created since we assume the older organization is the one we want to keep.
organizations = list(Organization.objects.filter(partner_id__in=[1, 4]).exclude(key='HarvardMedGlobalAcademy') \
                     .order_by('key', 'created'))

for key, group in groupby(organizations, lambda o: o.key):
    group = list(group)
    group_count = len(group)
    if group_count != 2:
        logger.warning('Organization [%s] has %d entries! Skipping.', key, group_count)
        continue

    # This is currently (incorrectly) associated with the HMS partner, but we will correct this.
    edx_org = group[0]

    # This is currently (incorrectly) associated with the edX partner. This organization will be deleted.
    hms_org = group[1]

    with transaction.atomic():
        # Update all data pointing to the more-recent organization to point to the older organization, which
        # was originally linked to the edX partner.
        Position.objects.objects.filter(organization_id=hms_org).update(organization_id=edx_org)
        Course.authoring_organizations.through.objects.filter(organization_id=hms_org).update(organization_id=edx_org)
        Course.sponsoring_organizations.through.objects.filter(organization_id=hms_org).update(organization_id=edx_org)
        Program.authoring_organizations.through.objects.filter(organization_id=hms_org).update(organization_id=edx_org)
        Program.credit_backing_organizations.through.objects.filter(organization_id=hms_org).update(
            organization_id=edx_org)

        # TODO Verify no data is associated with the HMS organization

        hms_org.delete()
        edx_org.partner_id = 1
        edx_org.save()
