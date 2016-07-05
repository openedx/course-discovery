from django.contrib import admin

from course_discovery.apps.publisher.models import Status, WorkflowCourseRun, WorkflowProgram

admin.site.register(Status)
admin.site.register(WorkflowCourseRun)
admin.site.register(WorkflowProgram)
