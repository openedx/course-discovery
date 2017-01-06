from django.contrib import admin
from guardian.admin import GuardedModelAdmin

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
class OrganizationExtensionAdmin(GuardedModelAdmin):
    pass
