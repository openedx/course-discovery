"""Custom API throttles."""
from django.core.cache import InvalidCacheBackendError, caches
from rest_framework.throttling import UserRateThrottle

from course_discovery.apps.core.models import UserThrottleRate
from course_discovery.apps.publisher.utils import is_publisher_user


def throttling_cache():
    """
    Returns the cache specifically used for throttling.
    """
    try:
        return caches['throttling']
    except InvalidCacheBackendError:
        return caches['default']


class OverridableUserRateThrottle(UserRateThrottle):
    """Rate throttling of requests, overridable on a per-user basis."""
    cache = throttling_cache()

    def allow_request(self, request, view):
        user = request.user

        if user and user.is_authenticated:
            try:
                # Override this throttle's rate if applicable
                user_throttle = UserThrottleRate.objects.get(user=user)
                self.rate = user_throttle.rate
                self.num_requests, self.duration = self.parse_rate(self.rate)
            except UserThrottleRate.DoesNotExist:
                # If we don't have a custom user override, skip throttling if they are a privileged user
                if user.is_superuser or user.is_staff or is_publisher_user(user):
                    return True

        return super().allow_request(request, view)
