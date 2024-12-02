""" API v1 URLs. """
from rest_framework import routers

from course_discovery.apps.learner_pathway.api.v1 import views

router = routers.SimpleRouter()
router.register(r'learner-pathway', views.LearnerPathwayViewSet, basename='learner-pathway')
router.register(r'learner-pathway-step', views.LearnerPathwayStepViewSet, basename='learner-pathway-step')
router.register(r'learner-pathway-course', views.LearnerPathwayCourseViewSet, basename='learner-pathway-course')
router.register(r'learner-pathway-program', views.LearnerPathwayProgramViewSet, basename='learner-pathway-program')
router.register(r'learner-pathway-block', views.LearnerPathwayBlocViewSet)

urlpatterns = router.urls
