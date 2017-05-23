from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import assign_perm

from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import (LEGAL_TEAM_GROUP_NAME, PARTNER_MANAGER_GROUP_NAME,
                                                       PROJECT_COORDINATOR_GROUP_NAME, PUBLISHER_GROUP_NAME,
                                                       REVIEWER_GROUP_NAME)
from course_discovery.apps.publisher.forms import (CourseRunAdminForm, CourseUserRoleForm, OrganizationUserRoleForm,
                                                   PublisherUserCreationForm, UserAttributesAdminForm)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension, OrganizationUserRole, PublisherUser, Seat,
                                                    UserAttributes)


@admin.register(CourseUserRole)
class CourseUserRoleAdmin(admin.ModelAdmin):
    form = CourseUserRoleForm
    raw_id_fields = ('changed_by',)
    list_display = ['role', 'course', 'user']
    search_fields = ['course__title']


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(GuardedModelAdmin):

    def save_model(self, request, obj, form, change):
        obj.save()

        # Assign EDIT/VIEW permissions to organization group.
        course_team_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN,
            OrganizationExtension.EDIT_COURSE_RUN
        ]
        self.assign_permissions(obj, obj.group, course_team_permissions)

        # Assign EDIT_COURSE permission to Marketing Reviewers group.
        marketing_permissions = [
            OrganizationExtension.EDIT_COURSE,
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self.assign_permissions(obj, Group.objects.get(name=REVIEWER_GROUP_NAME), marketing_permissions)

        # Assign EDIT_COURSE_RUN permission to Project Coordinators group.
        pc_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.EDIT_COURSE_RUN,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self.assign_permissions(obj, Group.objects.get(name=PROJECT_COORDINATOR_GROUP_NAME), pc_permissions)

        # Assign view permissions to Legal Team group.
        legal_team_permissions = [
            OrganizationExtension.VIEW_COURSE,
            OrganizationExtension.VIEW_COURSE_RUN
        ]
        self.assign_permissions(obj, Group.objects.get(name=LEGAL_TEAM_GROUP_NAME), legal_team_permissions)

    def assign_permissions(self, obj, group, permissions):
        for permission in permissions:
            assign_perm(permission, group, obj)


@admin.register(UserAttributes)
class UserAttributesAdmin(admin.ModelAdmin):
    form = UserAttributesAdminForm


@admin.register(OrganizationUserRole)
class OrganizationUserRoleAdmin(admin.ModelAdmin):
    form = OrganizationUserRoleForm
    list_display = ['role', 'organization', 'user']
    search_fields = ['organization__name']
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
            obj.user.groups.add(group)


@admin.register(CourseState)
class CourseStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
    list_display = ['name', 'approved_by_role', 'owner_role', 'course', 'marketing_reviewed']
    search_fields = ['name']


@admin.register(CourseRunState)
class CourseRunStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
    list_display = ['id', 'name', 'approved_by_role', 'owner_role',
                    'course_run', 'owner_role_modified', 'preview_accepted']
    search_fields = ['id', 'name']
    ordering = ['id']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
    list_display = ['title', 'number']
    search_fields = ['title', 'number']


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    form = CourseRunAdminForm
    raw_id_fields = ('changed_by',)
    list_display = ['course_name', 'lms_course_id', 'start', 'end']
    search_fields = ['id', 'lms_course_id', 'course__title']

    def course_name(self, obj):
        return obj.course.title


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(PublisherUser)
class PublisherUserAdmin(UserAdmin):
    add_form_template = 'publisher/admin/add_user_form.html'
    add_fieldsets = (
        (None, {'fields': ('username', 'groups',)}),
    )
    add_form = PublisherUserCreationForm

    def get_queryset(self, request):
        """
        Return only those users which belongs to any group.
        """
        return self.model.objects.filter(groups__in=Group.objects.all()).distinct()
