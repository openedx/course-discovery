from django.contrib import admin

from course_discovery.apps.publisher.models import Status, CourseRunDetail

admin.site.register(Status)
admin.site.register(CourseRunDetail)
