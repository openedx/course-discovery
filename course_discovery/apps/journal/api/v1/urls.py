""" API v1 URLs. """
from rest_framework.routers import DefaultRouter

from .views import JournalBundleViewSet, JournalViewSet

router = DefaultRouter()
router.register(r'journals', JournalViewSet, basename='journal')
router.register(r'journal_bundles', JournalBundleViewSet, basename='journal_bundle')
urlpatterns = router.urls
