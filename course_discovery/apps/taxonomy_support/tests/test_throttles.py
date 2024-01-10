from django.urls import reverse
from rest_framework.test import APITestCase


class ThrottleTest(APITestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('taxonomy_support:course_recommendations', args=('NO+COURSE',))

    def _make_requests(self, count=11):
        """
        Make multiple requests until the throttle's limit is exceeded.
        """
        for __ in range(count - 1):
            response = self.client.get(self.url)
            assert response.status_code != 429
        response = self.client.get(self.url)
        return response

    def assert_rate_limited(self, count=11):
        """
        Asserts that the throttle's rate limit exceeded and 429 error was raised.
        """
        response = self._make_requests(count)
        assert response.status_code == 429

    def test_rate_limit_not_exceeded(self):
        """
        Asserts that requests below throttle rate do not encounter 429.
        """
        response = self._make_requests(9)
        assert response.status_code != 429

    def test_rate_limiting(self):
        """
        Verify the API responds with HTTP 429 if the request goes over the rate limit.
        """
        self.assert_rate_limited(count=11)
