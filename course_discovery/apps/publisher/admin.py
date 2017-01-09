from django.contrib import admin
from django.contrib.auth.models import Permission
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import assign_perm, get_perms, remove_perm

from course_discovery.apps.publisher.forms import OrganizationExtensionAdminForm
from course_discovery.apps.publisher.models import (
    Course, CourseRun, CourseUserRole, OrganizationExtension, OrganizationUserRole, Seat, State, UserAttributes
)


admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(OrganizationUserRole)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)


@admin.register(CourseUserRole)
class CourseUserRoleAdmin(admin.ModelAdmin):
    raw_id_fields = ('user',)


@admin.register(OrganizationExtension)
class OrganizationExtensionAdmin(admin.ModelAdmin):

    list_display = ('organization', 'group', 'permissions',)
    list_per_page = 30
    form = OrganizationExtensionAdminForm

    def permissions(self, obj):
        return ", ".join([str(run) for run in get_perms(obj.group, obj)])

    permissions.short_description = _('Assigned Permissions')

    def save_model(self, request, obj, form, change):
        super(OrganizationExtensionAdmin, self).save_model(request, obj, form, change)
        if 'permissions' in form.changed_data:
            # remove all existing perms
            for permission in get_perms(obj.group, obj):
                remove_perm(permission, obj.group, obj)

            # add permissions
            new_permissions = Permission.objects.filter(id__in=request.POST.getlist('permissions'))
            for permission in new_permissions:
                assign_perm(permission.codename, obj.group, obj)
