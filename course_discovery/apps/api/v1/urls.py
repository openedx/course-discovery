""" API v1 URLs. """
from django.conf.urls import include, url
from rest_framework import routers

from course_discovery.apps.api.v1 import views

partners_router = routers.SimpleRouter()
partners_router.register(r'affiliate_window/catalogs', views.AffiliateWindowViewSet, base_name='affiliate_window')
partners_urls = partners_router.urls
urlpatterns = [
    url(r'^partners/', include(partners_urls, namespace='partners')),
]

router = routers.SimpleRouter()
router.register(r'catalogs', views.CatalogViewSet)
router.register(r'courses', views.CourseViewSet, base_name='course')
router.register(r'course_runs', views.CourseRunViewSet, base_name='course_run')
router.register(r'management', views.ManagementViewSet, base_name='management')
router.register(r'search/all', views.AggregateSearchViewSet, base_name='search-all')
router.register(r'search/courses', views.CourseSearchViewSet, base_name='search-courses')
router.register(r'search/course_runs', views.CourseRunSearchViewSet, base_name='search-course_runs')

urlpatterns += router.urls
