from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.publisher.forms import CourseUserRoleForm, OrganizationUserRoleForm, UserAttributesAdminForm
from course_discovery.apps.publisher.models import (
    Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
    OrganizationExtension, OrganizationUserRole, Seat, State,
    UserAttributes
)


@admin.register(CourseUserRole)
class CourseUserRoleAdmin(admin.ModelAdmin):
    form = CourseUserRoleForm
    raw_id_fields = ('changed_by',)


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(GuardedModelAdmin):
    pass


@admin.register(UserAttributes)
class UserAttributesAdmin(admin.ModelAdmin):
    form = UserAttributesAdminForm


@admin.register(OrganizationUserRole)
class OrganizationUserRoleAdmin(admin.ModelAdmin):
    form = OrganizationUserRoleForm


@admin.register(CourseState)
class CourseStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(CourseRunState)
class CourseRunStateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
