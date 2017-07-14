from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.publisher.assign_permissions import assign_permissions
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.constants import (INTERNAL_USER_GROUP_NAME, PARTNER_MANAGER_GROUP_NAME,
                                                       PROJECT_COORDINATOR_GROUP_NAME, PUBLISHER_GROUP_NAME,
                                                       REVIEWER_GROUP_NAME)
from course_discovery.apps.publisher.forms import (CourseRunAdminForm, OrganizationExtensionForm,
                                                   PublisherUserCreationForm, UserAttributesAdminForm)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension, OrganizationUserRole, PublisherUser, Seat,
                                                    UserAttributes)


@admin.register(CourseUserRole)
class CourseUserRoleAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by', 'course', 'user',)
    list_display = ['role', 'course', 'user']
    search_fields = ['course__title']


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(GuardedModelAdmin):
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
class OrganizationUserRoleAdmin(admin.ModelAdmin):
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
        obj.save()
        publisher_courses = obj.organization.publisher_courses

        courses_without_role = publisher_courses.exclude(course_user_roles__role=obj.role)

        CourseUserRole.objects.bulk_create(
            [CourseUserRole(course=course, user=obj.user, role=obj.role) for course in courses_without_role]
        )

        CourseUserRole.objects.filter(course__organizations__in=[obj.organization], role=obj.role).update(user=obj.user)

        # Assign user a group according to its role.
        group = Group.objects.get(name=self.role_groups_dict.get(obj.role))
        if group not in obj.user.groups.all():
            obj.user.groups.add(*(group, Group.objects.get(name=INTERNAL_USER_GROUP_NAME)))


@admin.register(CourseState)
class CourseStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
    list_display = ['id', 'name', 'approved_by_role', 'owner_role', 'course', 'marketing_reviewed']
    search_fields = ['id', 'course__title']
    list_filter = ('name',)


@admin.register(CourseRunState)
class CourseRunStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
    list_display = ['id', 'name', 'approved_by_role', 'owner_role',
                    'course_run', 'owner_role_modified', 'preview_accepted']
    list_filter = ('name',)
    search_fields = ['id', 'course_run__course__title']
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
    list_display = ['course_run', 'type']
    search_fields = ['course_run__course__title', 'type']


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
