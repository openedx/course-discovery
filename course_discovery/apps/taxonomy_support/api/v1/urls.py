from django.urls import re_path

from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX
from course_discovery.apps.taxonomy_support.api.v1.views import CourseRecommendationsAPIView

urlpatterns = [
    re_path(
        f'course_recommendations/(?P<course_key>{COURSE_ID_REGEX})/$',
        CourseRecommendationsAPIView.as_view(), name='course_recommendations'
    ),
]
