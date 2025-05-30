""" API v1 URLs. """
from django.conf.urls import include, url
from django.views.decorators.csrf import csrf_exempt
from rest_framework_nested import routers

from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.api.v1.views.programs import ProgramCoursesViewSet
from course_discovery.apps.course_metadata.views import CourseMetadataRefresher


partners_router = routers.SimpleRouter()

urlpatterns = [
    url(r'^partners/', include(partners_router.urls, namespace='partners')),
    url(r'^refresh_course_metadata/', csrf_exempt(CourseMetadataRefresher.as_view()), name='refresh-course-metadata')
]

router = routers.SimpleRouter()

router.register(r'programs', ProgramViewSet, base_name='program')
program_courses_router = routers.NestedSimpleRouter(router, r'programs', lookup=r'program')
program_courses_router.register(r'courses', ProgramCoursesViewSet, base_name=r'courses')

urlpatterns += router.urls
urlpatterns += program_courses_router.urls
