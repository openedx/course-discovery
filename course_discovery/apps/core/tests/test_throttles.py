import pytest
from django.urls import reverse

from course_discovery.apps.core.models import UserThrottleRate
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.throttles import OverridableUserRateThrottle


@pytest.mark.django_db
@pytest.mark.usefixtures('django_cache', 'partner')
class TestRateLimiting:
    """
    Testing rate limiting of API calls.
    """
    client = None
    user = None

    @pytest.fixture(autouse=True)
    def setup(self, client):
        self.user = UserFactory()
        client.login(username=self.user.username, password=USER_PASSWORD)
        self.client = client

    def _make_requests(self):
        """ Make multiple requests until the throttle's limit is exceeded.

        Returns
            Response: Response of the last request.
        """
        num_requests = OverridableUserRateThrottle().num_requests
        url = reverse('api_docs')

        for __ in range(num_requests + 1):
            response = self.client.get(url)

        return response

    def test_rate_limiting(self):
        """ Verify the API responds with HTTP 429 if a normal user exceeds the rate limit. """
        response = self._make_requests()

        assert response.status_code == 429

    def test_user_throttle_rate(self):
        """ Verify the UserThrottleRate can be used to override the default rate limit. """
        UserThrottleRate.objects.create(user=self.user, rate='1000/day')
        self.assert_rate_limit_successfully_exceeded()

    def assert_rate_limit_successfully_exceeded(self):
        """ Asserts that the throttle's rate limit can be exceeded without encountering an error. """
        response = self._make_requests()

        assert response.status_code == 200

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
