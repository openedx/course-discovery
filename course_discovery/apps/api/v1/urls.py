""" API v1 URLs. """
from django.conf.urls import include, url
from django.views.decorators.csrf import csrf_exempt
from rest_framework_nested import routers

from course_discovery.apps.api.v1.views import search as search_views
from course_discovery.apps.api.v1.views.affiliates import AffiliateWindowViewSet
from course_discovery.apps.api.v1.views.catalog_queries import CatalogQueryContainsViewSet
from course_discovery.apps.api.v1.views.catalogs import CatalogViewSet
from course_discovery.apps.api.v1.views.course_runs import CourseRunViewSet
from course_discovery.apps.api.v1.views.courses import CourseViewSet
from course_discovery.apps.api.v1.views.currency import CurrencyView
from course_discovery.apps.api.v1.views.organizations import OrganizationViewSet
from course_discovery.apps.api.v1.views.people import PersonViewSet
from course_discovery.apps.api.v1.views.program_types import ProgramTypeViewSet
from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.api.v1.views.programs import ProgramCoursesViewSet
from course_discovery.apps.api.v1.views.subjects import SubjectViewSet
from course_discovery.apps.api.v1.views.topics import TopicViewSet
from course_discovery.apps.course_metadata.views import CourseMetadataRefresher


partners_router = routers.SimpleRouter()
partners_router.register(r'affiliate_window/catalogs', AffiliateWindowViewSet, base_name='affiliate_window')

urlpatterns = [
    url(r'^partners/', include(partners_router.urls, namespace='partners')),
    url(r'search/typeahead', search_views.TypeaheadSearchView.as_view(), name='search-typeahead'),
    url(r'currency', CurrencyView.as_view(), name='currency'),
    url(r'^catalog/query_contains/?', CatalogQueryContainsViewSet.as_view(), name='catalog-query_contains'),
    url(r'^refresh_course_metadata/', csrf_exempt(CourseMetadataRefresher.as_view()), name='refresh-course-metadata')
]

router = routers.SimpleRouter()
router.register(r'catalogs', CatalogViewSet)
router.register(r'courses', CourseViewSet, base_name='course')
router.register(r'course_runs', CourseRunViewSet, base_name='course_run')
router.register(r'organizations', OrganizationViewSet, base_name='organization')
router.register(r'people', PersonViewSet, base_name='person')
router.register(r'subjects', SubjectViewSet, base_name='subject')
router.register(r'topics', TopicViewSet, base_name='topic')
router.register(r'program_types', ProgramTypeViewSet, base_name='program_type')
router.register(r'search/all', search_views.AggregateSearchViewSet, base_name='search-all')
router.register(r'search/courses', search_views.CourseSearchViewSet, base_name='search-courses')
router.register(r'search/course_runs', search_views.CourseRunSearchViewSet, base_name='search-course_runs')
router.register(r'search/programs', search_views.ProgramSearchViewSet, base_name='search-programs')

router.register(r'programs', ProgramViewSet, base_name='program')
program_courses_router = routers.NestedSimpleRouter(router, r'programs', lookup=r'program')
program_courses_router.register(r'courses', ProgramCoursesViewSet, base_name=r'courses')

urlpatterns += router.urls
urlpatterns += program_courses_router.urls
