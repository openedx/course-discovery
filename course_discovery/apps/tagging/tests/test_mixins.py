from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.http.response import HttpResponse
from django.test import RequestFactory, TestCase
from django.views import View

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.tagging.mixins import VerticalTaggingAdministratorPermissionRequiredMixin


class MockView(VerticalTaggingAdministratorPermissionRequiredMixin, View):
    """A mock view to test the mixin."""

    def get(self, request, *args, **kwargs):
        return HttpResponse("Success!")


class VerticalTaggingAdministratorPermissionRequiredMixinTests(TestCase):
    """Tests for VerticalTaggingAdministratorPermissionRequiredMixin."""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = MockView.as_view()

        self.superuser = UserFactory(is_staff=True, is_superuser=True)
        self.vertical_admin = UserFactory(is_staff=True, is_superuser=False)
        self.regular_user = UserFactory(is_staff=False, is_superuser=False)

        self.allowed_group = Group.objects.create(name=settings.VERTICALS_MANAGEMENT_GROUPS[0])
        self.vertical_admin.groups.add(self.allowed_group)

    def test_user_not_authenticated(self):
        """Test that unauthenticated users are forbidden."""
        request = self.factory.get("/")
        request.user = AnonymousUser()

        response = self.view(request)
        self.assertEqual(response.status_code, 302)

    def test_regular_user(self):
        """Test that users not in the allowed group or superuser are forbidden."""
        request = self.factory.get("/")
        request.user = self.regular_user
        with self.assertRaises(PermissionDenied):
            self.view(request)

    def test_user_in_allowed_group(self):
        """Test that users in the allowed group can access the view."""
        request = self.factory.get("/")
        request.user = self.vertical_admin

        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Success!")

    def test_superuser_access(self):
        """Test that superusers can access the view."""
        self.superuser.groups.clear()

        request = self.factory.get("/")
        request.user = self.superuser

        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Success!")
