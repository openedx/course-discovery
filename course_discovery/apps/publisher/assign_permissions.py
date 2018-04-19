from django.contrib.auth.models import Group
from guardian.shortcuts import assign_perm

from course_discovery.apps.publisher.constants import (
    GENERAL_STAFF_GROUP_NAME, LEGAL_TEAM_GROUP_NAME, PARTNER_SUPPORT_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME,
    REVIEWER_GROUP_NAME
)
from course_discovery.apps.publisher.models import OrganizationExtension


def assign_permissions(organization_extension):
    # Assign EDIT/VIEW permissions to organization group.
    course_team_permissions = [
        OrganizationExtension.VIEW_COURSE,
        OrganizationExtension.EDIT_COURSE,
        OrganizationExtension.VIEW_COURSE_RUN,
        OrganizationExtension.EDIT_COURSE_RUN
    ]
    assign_permissions_to_group(organization_extension, organization_extension.group, course_team_permissions)
    # Assign EDIT_COURSE permission to Marketing Reviewers group.
    marketing_permissions = [
        OrganizationExtension.EDIT_COURSE,
        OrganizationExtension.VIEW_COURSE,
        OrganizationExtension.VIEW_COURSE_RUN
    ]
    assign_permissions_to_group(organization_extension, Group.objects.get(name=REVIEWER_GROUP_NAME),
                                marketing_permissions)
    # Assign EDIT_COURSE_RUN permission to Project Coordinators group.
    pc_permissions = [
        OrganizationExtension.VIEW_COURSE,
        OrganizationExtension.EDIT_COURSE_RUN,
        OrganizationExtension.VIEW_COURSE_RUN
    ]
    assign_permissions_to_group(organization_extension, Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME),
                                pc_permissions)
    # Assign view permissions to Legal Team group.
    view_permissions = [
        OrganizationExtension.VIEW_COURSE,
        OrganizationExtension.VIEW_COURSE_RUN
    ]
    assign_permissions_to_group(organization_extension, Group.objects.get(name=LEGAL_TEAM_GROUP_NAME),
                                view_permissions)
    assign_permissions_to_group(organization_extension, Group.objects.get(name=GENERAL_STAFF_GROUP_NAME),
                                view_permissions)
    assign_permissions_to_group(organization_extension, Group.objects.get(name=PARTNER_SUPPORT_GROUP_NAME),
                                view_permissions)


def assign_permissions_to_group(organization_extension, group, permissions):
    for permission in permissions:
        assign_perm(permission, group, organization_extension)
