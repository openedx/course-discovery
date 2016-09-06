from django.contrib import admin

from course_discovery.apps.publisher.models import Course, CourseRun, Seat, State, UserAttribute

admin.site.register(Course)
admin.site.register(CourseRun)
admin.site.register(Seat)
admin.site.register(State)
admin.site.register(UserAttribute)
