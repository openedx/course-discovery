from django.contrib import admin

from course_discovery.apps.publisher.models import (
    Course, CourseRun, OrganizationGroup, OrganizationRoles,
    Seat, State, UserAttributes, UserRole
)

admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(OrganizationGroup)
admin.site.register(OrganizationRoles)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)
admin.site.register(UserRole)

