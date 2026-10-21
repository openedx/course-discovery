from unittest.mock import patch

import ddt
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.tests.jwt_utils import generate_jwt_header_for_user
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.models import UserThrottleRate
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.throttles import OverridableUserRateThrottle, throttling_cache
from course_discovery.apps.publisher.tests.factories import GroupFactory


@ddt.ddt
class RateLimitingExceededTest(SiteMixin, APITestCase):
    """
    Testing rate limiting of API calls.
    """

    def setUp(self):
        super().setUp()

        self.url = reverse('api_docs')
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def tearDown(self):
        super().tearDown()
        throttling_cache().clear()

    def _build_jwt_headers(self, user, payload=None):
        """
        Helper function for creating headers for the JWT authentication.
        """
        token = generate_jwt_header_for_user(user, payload)
        headers = {'HTTP_AUTHORIZATION': token}
        return headers

    def _make_requests(self, count=None, **headers):
        """ Make multiple requests until the throttle's limit is exceeded.

        Returns
            Response: Response of the last request.
        """
        count = count or 6
        user_rates = {'user': '5/hour'}
        with patch('rest_framework.views.APIView.throttle_classes', (OverridableUserRateThrottle,)):
            with patch.object(OverridableUserRateThrottle, 'THROTTLE_RATES', user_rates):
                for __ in range(count - 1):
                    response = self.client.get(self.url, **headers)
                    assert response.status_code == 200
                response = self.client.get(self.url, **headers)
        return response

    def assert_rate_limit_successfully_exceeded(self, **headers):
        """ Asserts that the throttle's rate limit can be exceeded without encountering an error. """
        response = self._make_requests(**headers)
        assert response.status_code == 200

    def assert_rate_limited(self, count=None, **headers):
        """ Asserts that the throttle's rate limit was exceeded and we were denied. """
        response = self._make_requests(count, **headers)
        assert response.status_code == 429

    def test_rate_limiting(self):
        """ Verify the API responds with HTTP 429 if a normal user exceeds the rate limit. """
        self.assert_rate_limited()

    def test_user_throttle_rate(self):
        """ Verify the UserThrottleRate can be used to override the default rate limit. """
        UserThrottleRate.objects.create(user=self.user, rate='10/hour')
        self.assert_rate_limited(11)

    def test_superuser_throttling(self):
        """ Verify superusers are not throttled. """
        self.user.is_superuser = True
        self.user.save()
        self.assert_rate_limit_successfully_exceeded()

    def test_staff_throttling(self):
        """ Verify staff users are not throttled. """
        self.user.is_staff = True
        self.user.save()
        self.assert_rate_limit_successfully_exceeded()

    def test_publisher_user_throttling(self):
        """ Verify publisher users are not throttled. """
        self.user.groups.add(GroupFactory())
        self.assert_rate_limit_successfully_exceeded()

    def test_staff_with_user_throttle_rate(self):
        """ Verify the UserThrottleRate kicks in even for staff. """
        self.user.is_staff = True
        self.user.save()
        UserThrottleRate.objects.create(user=self.user, rate='10/hour')
        self.assert_rate_limited(11)

    @ddt.data(
        ([], True),
        (['enterprise_learner:*'], False),
        (['enterprise_admin:*'], False),
        (['enterprise_openedx_operator:*'], False),
    )
    @ddt.unpack
    @override_settings(ENHANCED_THROTTLE_LIMIT='10/hour')
    def test_enterprise_user_throttling_with_jwt_authentication(self, jwt_roles, is_rate_limited):
        """ Verify enterprise users are throttled at a higher rate. """
        payload = {
            'roles': jwt_roles,
        }
        headers = self._build_jwt_headers(self.user, payload)
        if is_rate_limited:
            self.assert_rate_limited(**headers)
        else:
            self.assert_rate_limit_successfully_exceeded(count=5, **headers)
            self.assert_rate_limited(**headers)
