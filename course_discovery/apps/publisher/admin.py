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
from course_discovery.apps.publisher.forms import OrganizationExtensionForm, UserAttributesAdminForm
from course_discovery.apps.publisher.models import (
    CourseUserRole, OrganizationExtension, OrganizationUserRole, UserAttributes
)


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(GuardedModelAdminMixin, SimpleHistoryAdmin):
    form = OrganizationExtensionForm
    list_display = ['organization', 'group']
    search_fields = ['organization__name', 'group__name']

    def save_model(self, request, obj, form, change):
        obj.save()
        assign_permissions(obj)


@admin.register(UserAttributes)
class UserAttributesAdmin(admin.ModelAdmin):
    form = UserAttributesAdminForm


@admin.register(OrganizationUserRole)
class OrganizationUserRoleAdmin(SimpleHistoryAdmin):
    raw_id_fields = ('user', 'organization',)
    list_display = ['role', 'organization', 'user']
    search_fields = ['organization__name']
    role_groups_dict = {
        InternalUserRole.MarketingReviewer: REVIEWER_GROUP_NAME,
        InternalUserRole.ProjectCoordinator: PROJECT_COORDINATOR_GROUP_NAME,
        InternalUserRole.Publisher: PUBLISHER_GROUP_NAME,
        InternalUserRole.PartnerManager: PARTNER_MANAGER_GROUP_NAME
    }

    def save_model(self, request, obj, form, change):
        # If trying to do an update, check to see if there's an original user associated with the model
        try:
            original_user = self.model.objects.get(id=obj.id).user
        except self.model.DoesNotExist:
            original_user = None

        obj.save()
        publisher_courses = obj.organization.publisher_courses

        courses_without_role = publisher_courses.exclude(course_user_roles__role=obj.role)

        CourseUserRole.objects.bulk_create(
            [CourseUserRole(course=course, user=obj.user, role=obj.role) for course in courses_without_role]
        )

        if original_user:
            CourseUserRole.objects.filter(
                course__organizations__in=[obj.organization],
                role=obj.role,
                user=original_user,
            ).update(user=obj.user)
        else:
            CourseUserRole.objects.filter(
                course__organizations__in=[obj.organization],
                role=obj.role,
            ).update(user=obj.user)

        # Assign user a group according to its role.
        group = Group.objects.get(name=self.role_groups_dict.get(obj.role))
        if group not in obj.user.groups.all():
            obj.user.groups.add(*(group, Group.objects.get(name=INTERNAL_USER_GROUP_NAME)))
