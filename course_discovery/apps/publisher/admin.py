from django.contrib import admin

from course_discovery.apps.publisher.models import Status, CourseRunDetail, WorkflowProgram

admin.site.register(Status)
admin.site.register(CourseRunDetail)
admin.site.register(WorkflowProgram)
