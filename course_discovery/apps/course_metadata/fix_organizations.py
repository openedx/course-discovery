import logging
from itertools import groupby

from django.db import transaction

from course_discovery.apps.course_metadata.models import Organization, Course, Position, Program

logger = logging.getLogger(__name__)

# 1. Sort by key as a prerequisite to groupby.
# 2. Sort by created since we assume the older organization is the one we want to keep.
organizations = list(Organization.objects.filter(partner_id__in=[1, 2]).exclude(key='HarvardMedGlobalAcademy').order_by('key', 'created'))

for key, group in groupby(organizations, lambda o: o.key):
    group = list(group)
    group_count = len(group)
    if group_count != 2:
        logger.warning('Organization [%s] has %d entries! Skipping.', key, group_count)
        print('Organization {} has {} entries! Skipping'.format(key, group_count))
        continue
    
    # This is currently (incorrectly) associated with the HMS partner, but we will correct this.
    edx_org = group[0]
    
    # This is currently (incorrectly) associated with the edX partner. This organization will be deleted.
    hms_org = group[1]
    logger.info('Delete organization links associated with [%s]', hms_org.key)
    print('Delete organization links associated with {}'.format(hms_org.key))
    
    with transaction.atomic():
        # Update all data pointing to the more-recent organization to point to the older organization, which
        # was originally linked to the edX partner.
        Position.objects.filter(organization_id=hms_org).update(organization_id=edx_org)
        Course.authoring_organizations.through.objects.filter(organization_id=hms_org).delete()
        Course.sponsoring_organizations.through.objects.filter(organization_id=hms_org).delete()
        Program.authoring_organizations.through.objects.filter(organization_id=hms_org).delete()
        Program.credit_backing_organizations.through.objects.filter(organization_id=hms_org).delete()
        
        # TODO Verify no data is associated with the HMS organization
        logger.info('Start deleting organization [%s] that was associated with edX', hms_org.key)
        print('Start deleting organization {} that was associated with edX'.format(hms_org.key))
        hms_org.delete()
        logger.info('Update organization [%s] to have edX as partner', edx_org.key)
        print('Update organization {} to have edX as partner'.format(edx_org.key))
        edx_org.partner_id = 1
        edx_org.save()
