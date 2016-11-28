from django.contrib import admin

from course_discovery.apps.publisher.models import (
    Course, CourseRun, GroupOrganization, OrganizationUserRole, Seat, State, UserAttributes
)

admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(GroupOrganization)
admin.site.register(OrganizationUserRole)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttributes)
