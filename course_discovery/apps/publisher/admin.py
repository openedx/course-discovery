from django.contrib import admin

from course_discovery.apps.publisher.models import (
    Course, CourseRun, Seat, State, UserAttributes, OrganizationsRoles, OrganizationsGroup
)


@admin.register(OrganizationsRoles)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user', 'role',)
    list_filter = ('organization',)
    search_fields = ('organization', 'user', 'role',)


admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)
admin.site.register(OrganizationsGroup)

