from django.test.utils import override_settings
from django.urls import path, reverse
from mock import patch
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.test import APITestCase
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from course_discovery.apps.api.mixins import AnonymousUserThrottleAuthenticatedEndpointMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory


class TestAPIView(AnonymousUserThrottleAuthenticatedEndpointMixin, APIView):
    anonymous_user_throttle_class = None
    permission_classes = ()
    authentication_classes = ()

    def get(self, request, *_args, **_kwargs):
        return Response(
            status=status.HTTP_200_OK,
            data="Hello, World"
        )


class TestThrottle(AnonRateThrottle):
    rate = '5/hour'


# Replaces the built url with the urlpatterns defined in the test file so that TestView can be accessed
# via an url
urlpatterns = [
    path('test', TestAPIView.as_view(), name='test-view'),
]


@override_settings(ROOT_URLCONF=__name__)
class TestAnonymousUserThrottleMixin(APITestCase):

    def setUp(self):
        super().setUp()
        self.url = reverse('test-view')

    def make_requests(self, count=5):
        """
        Make multiple requests until the throttle's limit is exceeded.
        """
        for __ in range(count - 1):
            response = self.client.get(self.url)
            assert response.status_code != 429
        response = self.client.get(self.url)
        return response

    def test_throttle_authenticated_user(self):
        """
        Verify that anonymous user throttle does not apply to authenticated users.
        """
        auth_user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=auth_user.username, password=USER_PASSWORD)
        with patch.object(TestAPIView, 'anonymous_user_throttle_class', TestThrottle):
            with patch.object(
                    TestAPIView, 'authentication_classes', api_settings.DEFAULT_AUTHENTICATION_CLASSES
            ):
                response = self.make_requests(10)
        assert response.status_code == 200
        assert response.data == "Hello, World"
        self.client.logout()

    def test_throttle_limit__authentication_classes(self):
        """
        Verify that endpoint is throttled against unauthenticated users when requests are greater than limit.
        """
        with patch.object(TestAPIView, 'anonymous_user_throttle_class', TestThrottle):
            with patch.object(
                    TestAPIView, 'authentication_classes', api_settings.DEFAULT_AUTHENTICATION_CLASSES
            ):
                response = self.make_requests(6)
        assert response.status_code == 429

    def test_throttle_limit__no_authentication_permission(self):
        """
        Verify that anonymous user throttle does not execute if the view does not have auth defined via
        authentication_classes or IsAuthenticated permission.
        """
        with patch.object(TestAPIView, 'anonymous_user_throttle_class', TestThrottle):
            response = self.make_requests(10)
        assert response.status_code != 429

    def test_throttle_limit__authentication_permissions(self):
        """
        Verify that endpoint is throttled against unauthenticated users when IsAuthenticated permission is present
        on API endpoint.
        """
        with patch.object(TestAPIView, 'anonymous_user_throttle_class', TestThrottle):
            with patch.object(
                    TestAPIView, 'permission_classes', (IsAuthenticated, )
            ):
                response = self.make_requests(6)
        assert response.status_code == 429
