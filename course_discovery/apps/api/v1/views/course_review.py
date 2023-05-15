from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from course_discovery.apps.api.serializers import CourseReviewSerializer
from course_discovery.apps.course_metadata.models import CourseReview


class CourseReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """ CourseReview. """

    throttle_classes = [UserRateThrottle]
    throttle_rate = '150/hour'
    queryset = CourseReview.objects.all()
    serializer_class = CourseReviewSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = 'course_key'
