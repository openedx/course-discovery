from django.core.cache import cache
from django.core.urlresolvers import reverse

from rest_framework.test import APITestCase

from course_discovery.apps.core.models import UserThrottleRate
from course_discovery.apps.core.tests.factories import UserFactory, USER_PASSWORD
from course_discovery.apps.core.throttles import OverridableUserRateThrottle


class RateLimitingTest(APITestCase):
    """
    Testing rate limiting of API calls.
    """

    def setUp(self):
        super(RateLimitingTest, self).setUp()
        self.url = reverse('django.swagger.resources.view')
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def tearDown(self):
        """
        Clear the cache, since DRF uses it for recording requests against a
        URL. Django does not clear the cache between test runs.
        """
        super(RateLimitingTest, self).tearDown()
        cache.clear()

    def _make_requests(self):
        num_requests = OverridableUserRateThrottle().num_requests
        for __ in range(num_requests + 1):
            response = self.client.get(self.url)
        return response

    def test_rate_limiting(self):
        response = self._make_requests()
        self.assertEqual(response.status_code, 429)

    def test_user_throttle_rate(self):
        UserThrottleRate.objects.create(user=self.user, rate='1000/day')
        response = self._make_requests()
        self.assertEqual(response.status_code, 200)

    def test_superuser_throttling(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save()
        response = self._make_requests()
        self.assertEqual(response.status_code, 200)

    def test_anonymous_throttling(self):
        self.client.logout()
        self.test_rate_limiting()
