""" API v1 URLs. """
from rest_framework import routers

from course_discovery.apps.api.v1 import views

urlpatterns = []

router = routers.SimpleRouter()
router.register(r'catalogs', views.CatalogViewSet)
router.register(r'courses', views.CourseViewSet, base_name='course')
router.register(r'course_runs', views.CourseRunViewSet, base_name='course_run')
router.register(r'management', views.ManagementViewSet, base_name='management')

urlpatterns += router.urls
