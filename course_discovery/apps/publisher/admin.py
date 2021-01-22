from django.contrib import admin
from django.contrib.auth.models import Group
from guardian.admin import GuardedModelAdminMixin
from simple_history.admin import SimpleHistoryAdmin

from course_discovery.apps.publisher.assign_permissions import assign_permissions
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import (
    INTERNAL_USER_GROUP_NAME, PARTNER_MANAGER_GROUP_NAME, PROJECT_COORDINATOR_GROUP_NAME, PUBLISHER_GROUP_NAME,
    REVIEWER_GROUP_NAME
)
from course_discovery.apps.publisher.models import OrganizationExtension, OrganizationUserRole, UserAttributes


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(GuardedModelAdminMixin, SimpleHistoryAdmin):
    list_display = ['organization', 'group']
    search_fields = ['organization__name', 'group__name']
    autocomplete_fields = ['organization', 'group']

    def save_model(self, request, obj, form, change):
        obj.save()
        assign_permissions(obj)


@admin.register(UserAttributes)
class UserAttributesAdmin(admin.ModelAdmin):
    autocomplete_fields = ['user']


@admin.register(OrganizationUserRole)
class OrganizationUserRoleAdmin(SimpleHistoryAdmin):
    list_display = ['role', 'organization', 'user']
    search_fields = ['organization__name']
    autocomplete_fields = ['organization', 'user']
    role_groups_dict = {
        InternalUserRole.MarketingReviewer: REVIEWER_GROUP_NAME,
        InternalUserRole.ProjectCoordinator: PROJECT_COORDINATOR_GROUP_NAME,
        InternalUserRole.Publisher: PUBLISHER_GROUP_NAME,
        InternalUserRole.PartnerManager: PARTNER_MANAGER_GROUP_NAME
    }

    def save_model(self, request, obj, form, change):
        obj.save()

        # Assign user a group according to its role.
        group = Group.objects.get(name=self.role_groups_dict.get(obj.role))
        if group not in obj.user.groups.all():
            obj.user.groups.add(*(group, Group.objects.get(name=INTERNAL_USER_GROUP_NAME)))
