
from rest_framework.throttling import AnonRateThrottle


class CourseRecommendationsViewAnonymousUserThrottle(AnonRateThrottle):
    """
    Throttling for Anonymous users against CourseRecommendationsAPIView endpoint.
    """
    rate = '10/h'
