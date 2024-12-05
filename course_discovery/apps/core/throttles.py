"""Custom API throttles."""
from django.conf import settings
from django.core.cache import InvalidCacheBackendError, caches
from edx_rest_framework_extensions.auth.jwt.decoder import configured_jwt_decode_handler
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


def is_priviledged_user_with_enhanced_throttle(request):
    """
    Determine whether a JWT-authenticated user has increased throttling rates
    based on the `roles` in the decoded JWT token associated with the request.
    """
    jwt_token = request.auth
    if not jwt_token:
        return False
    decoded_jwt = configured_jwt_decode_handler(jwt_token)
    roles = decoded_jwt.get('roles', [])
    return any(
        privileged_role_keyword in role
        for privileged_role_keyword in settings.ENHANCED_THROTTLE_JWT_ROLE_KEYWORDS
        for role in roles
    )


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
            except UserThrottleRate.DoesNotExist:
                # If we don't have a custom user override, skip throttling if they are a privileged user
                if user.is_superuser or user.is_staff or is_publisher_user(user):
                    return True

                # If the user has privileged throttling limits, increase the rate
                if is_priviledged_user_with_enhanced_throttle(request):
                    self.rate = settings.ENHANCED_THROTTLE_LIMIT

        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)
