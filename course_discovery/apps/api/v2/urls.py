"""API v2 URLs."""

from rest_framework import routers

from course_discovery.apps.api.v2.views import search as search_views

app_name = 'v2'

router = routers.SimpleRouter()
router.register(r'search/all', search_views.AggregateSearchViewSet, basename='search-all')
urlpatterns = router.urls
