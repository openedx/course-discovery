""" API v1 URLs. """
from rest_framework.routers import DefaultRouter

from .views import JournalViewSet

router = DefaultRouter()
router.register(r'journals', JournalViewSet, base_name='journal')
urlpatterns = router.urls
