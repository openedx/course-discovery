from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from guardian.admin import GuardedModelAdmin

from course_discovery.apps.publisher.forms import (CourseUserRoleForm, OrganizationUserRoleForm,
                                                   PublisherUserCreationForm, UserAttributesAdminForm)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension, OrganizationUserRole, PublisherUser, Seat,
                                                    State, UserAttributes)


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


@admin.register(PublisherUser)
class PublisherUserAdmin(UserAdmin):
    add_form_template = 'publisher/admin/add_user_form.html'
    add_fieldsets = (
        (None, {'fields': ('username', 'groups',)}),
    )
    add_form = PublisherUserCreationForm

    def get_queryset(self, request):
        return self.model.objects.filter(groups__in=Group.objects.all()).distinct()
