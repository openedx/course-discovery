""" API v1 URLs. """
from rest_framework import routers

from course_discovery.apps.learner_pathway.api.v1 import views

router = routers.SimpleRouter()
router.register(r'learner-pathway', views.LearnerPathwayViewSet)
router.register(r'learner-pathway-step', views.LearnerPathwayStepViewSet)
router.register(r'learner-pathway-course', views.LearnerPathwayCourseViewSet)
router.register(r'learner-pathway-program', views.LearnerPathwayProgramViewSet)
router.register(r'learner-pathway-block', views.LearnerPathwayBlocViewSet)

urlpatterns = router.urls
