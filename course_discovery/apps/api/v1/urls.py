""" API v1 URLs. """
from django.conf.urls import include, url
from rest_framework import routers

from course_discovery.apps.api.v1.views import search as search_views
from course_discovery.apps.api.v1.views.affiliates import AffiliateWindowViewSet
from course_discovery.apps.api.v1.views.catalogs import CatalogViewSet
from course_discovery.apps.api.v1.views.course_runs import CourseRunViewSet
from course_discovery.apps.api.v1.views.courses import CourseViewSet
from course_discovery.apps.api.v1.views.programs import ProgramViewSet

partners_router = routers.SimpleRouter()
partners_router.register(r'affiliate_window/catalogs', AffiliateWindowViewSet, base_name='affiliate_window')

urlpatterns = [
    url(r'^partners/', include(partners_router.urls, namespace='partners')),
    url(r'search/typeahead', search_views.TypeaheadSearchView.as_view(), name='search-typeahead')
]

router = routers.SimpleRouter()
router.register(r'catalogs', CatalogViewSet)
router.register(r'courses', CourseViewSet, base_name='course')
router.register(r'course_runs', CourseRunViewSet, base_name='course_run')
router.register(r'programs', ProgramViewSet, base_name='program')
router.register(r'search/all', search_views.AggregateSearchViewSet, base_name='search-all')
router.register(r'search/courses', search_views.CourseSearchViewSet, base_name='search-courses')
router.register(r'search/course_runs', search_views.CourseRunSearchViewSet, base_name='search-course_runs')
router.register(r'search/programs', search_views.ProgramSearchViewSet, base_name='search-programs')

urlpatterns += router.urls
