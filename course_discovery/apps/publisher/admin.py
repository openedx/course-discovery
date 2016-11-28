from django.contrib import admin

from course_discovery.apps.publisher.models import (
    Course, CourseRun, CourseUserRole, OrganizationExtension, OrganizationUserRole, Seat, State, UserAttributes
)

admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(OrganizationExtension)
admin.site.register(OrganizationUserRole)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)


@admin.register(CourseUserRole)
class CourseUserRoleAdmin(admin.ModelAdmin):
    raw_id_fields = ('user',)
