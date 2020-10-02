""" API v1 URLs. """
from django.conf.urls import include, url
from rest_framework import routers

from course_discovery.apps.api.v1.views import search as search_views
from course_discovery.apps.api.v1.views.affiliates import AffiliateWindowViewSet, ProgramsAffiliateWindowViewSet
from course_discovery.apps.api.v1.views.catalog_queries import CatalogQueryContainsViewSet
from course_discovery.apps.api.v1.views.catalogs import CatalogViewSet
from course_discovery.apps.api.v1.views.collaborators import CollaboratorViewSet
from course_discovery.apps.api.v1.views.comments import CommentViewSet
from course_discovery.apps.api.v1.views.course_editors import CourseEditorViewSet
from course_discovery.apps.api.v1.views.course_runs import CourseRunViewSet
from course_discovery.apps.api.v1.views.courses import CourseViewSet
from course_discovery.apps.api.v1.views.currency import CurrencyView
from course_discovery.apps.api.v1.views.level_types import LevelTypeViewSet
from course_discovery.apps.api.v1.views.organizations import OrganizationViewSet
from course_discovery.apps.api.v1.views.pathways import PathwayViewSet
from course_discovery.apps.api.v1.views.people import PersonViewSet
from course_discovery.apps.api.v1.views.program_types import ProgramTypeViewSet
from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.api.v1.views.subjects import SubjectViewSet
from course_discovery.apps.api.v1.views.topics import TopicViewSet
from course_discovery.apps.api.v1.views.user_management import UsernameReplacementView

app_name = 'v1'

partners_router = routers.SimpleRouter()
partners_router.register(r'affiliate_window/catalogs', AffiliateWindowViewSet, basename='affiliate_window')
partners_router.register(
    r'affiliate_window/programs/catalogs',
    ProgramsAffiliateWindowViewSet,
    basename='programs_affiliate_window'
)

urlpatterns = [
    url(r'^partners/', include((partners_router.urls, 'partners'))),
    url(r'search/typeahead', search_views.TypeaheadSearchView.as_view(), name='search-typeahead'),
    url(r'^search/person_typeahead', search_views.PersonTypeaheadSearchView.as_view(), name='person-search-typeahead'),
    url(r'currency', CurrencyView.as_view(), name='currency'),
    url(r'^catalog/query_contains/?', CatalogQueryContainsViewSet.as_view(), name='catalog-query_contains'),
    url(r'^replace_usernames/$', UsernameReplacementView.as_view(), name="replace_usernames"),
]

router = routers.SimpleRouter()
router.register(r'catalogs', CatalogViewSet)
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'course_editors', CourseEditorViewSet, basename='course_editor')
router.register(r'course_runs', CourseRunViewSet, basename='course_run')
router.register(r'collaborators', CollaboratorViewSet, basename='collaborator')
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'people', PersonViewSet, basename='person')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'pathways', PathwayViewSet, basename='pathway')
router.register(r'programs', ProgramViewSet, basename='program')
router.register(r'level_types', LevelTypeViewSet, basename='level_type')
router.register(r'program_types', ProgramTypeViewSet, basename='program_type')
router.register(r'search/limited', search_views.LimitedAggregateSearchView, basename='search-limited')
router.register(r'search/all', search_views.AggregateSearchViewSet, basename='search-all')
router.register(r'search/courses', search_views.CourseSearchViewSet, basename='search-courses')
router.register(r'search/course_runs', search_views.CourseRunSearchViewSet, basename='search-course_runs')
router.register(r'search/programs', search_views.ProgramSearchViewSet, basename='search-programs')
router.register(r'search/people', search_views.PersonSearchViewSet, basename='search-people')

urlpatterns += router.urls
