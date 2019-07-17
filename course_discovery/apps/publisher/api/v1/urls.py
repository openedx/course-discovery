from rest_framework.routers import DefaultRouter

from .views import CourseRunViewSet

router = DefaultRouter()
router.register(r'course_runs', CourseRunViewSet, basename='course_run')
urlpatterns = router.urls
