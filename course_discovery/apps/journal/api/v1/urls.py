""" API v1 URLs. """
from rest_framework.routers import DefaultRouter

from .views import JournalViewSet, JournalBundleViewSet

router = DefaultRouter()
router.register(r'journals', JournalViewSet, base_name='journal')
router.register(r'journal_bundles', JournalBundleViewSet, base_name='journal_bundle')
urlpatterns = router.urls
