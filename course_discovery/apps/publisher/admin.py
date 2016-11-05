from django.contrib import admin
from django.utils.safestring import mark_safe

from course_discovery.apps.publisher.models import (
    Course, CourseRun, Seat, State, UserAttributes, OrganizationsRoles, OrganizationsGroup
)


@admin.register(OrganizationsRoles)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user', 'role',)
    list_filter = ('organization',)
    search_fields = ('organization', 'user', 'role',)



@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    readonly_fields = ('user_with_permissions_display',)

    def user_with_permissions_display(self, obj):
        return mark_safe("<br>".join([k.username + '-' + v[0] for k, v in obj.has_role_permissions.items()]))

    user_with_permissions_display.short_description = 'Users with permissions'


admin.site.register(CourseRun)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)
admin.site.register(OrganizationsGroup)

