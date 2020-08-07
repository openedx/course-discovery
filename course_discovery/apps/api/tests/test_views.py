import ddt
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.api.views import api_docs_permission_denied_handler
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory


class TestApiDocs(APITestCase):
    """
    Regression tests introduced following LEARNER-1590.
    """
    path = reverse('api_docs')

    def test_api_docs(self):
        """
        Verify that the API docs are available to authenticated clients.
        """
        user = UserFactory(is_staff=True)
        self.client.login(username=user.username, password=USER_PASSWORD)

        response = self.client.get(self.path)
        assert response.status_code == 200

    def test_api_docs_redirect(self):
        """
        Verify that unauthenticated clients are redirected.
        """
        response = self.client.get(self.path)
        assert response.status_code == 302


@ddt.ddt
class ApiDocsPermissionDeniedHandlerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request_path = '/'
        self.request = RequestFactory().get(self.request_path)

    def test_authenticated(self):
        """ Verify the view raises `PermissionDenied` if the request is authenticated. """
        user = UserFactory()
        self.request.user = user
        self.assertRaises(PermissionDenied, api_docs_permission_denied_handler, self.request)

    @ddt.data(None, AnonymousUser())
    def test_not_authenticated(self, user):
        """ Verify the view redirects to the login page if the request is not authenticated. """
        self.request.user = user
        response = api_docs_permission_denied_handler(self.request)
        expected_url = '{path}?next={next}'.format(path=reverse('login'), next=self.request_path)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)
