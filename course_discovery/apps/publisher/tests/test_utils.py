from django.test import TestCase

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.utils import is_email_notification_enabled, is_publisher_user


class PublisherUtilsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_email_notification_enabled_by_default(self):
        """ Test email notification is enabled for the user by default."""

        assert not hasattr(self.user, 'attributes')

        # Verify email notifications are enabled for user without associated attributes
        assert is_email_notification_enabled(self.user) is True

    def test_is_email_notification_enabled(self):
        """ Test email notification enabled/disabled for the user."""

        user_attribute = factories.UserAttributeFactory(user=self.user)

        # Verify email notifications are enabled for user with associated attributes,
        # but no explicit value set for the enable_email_notification attribute
        assert is_email_notification_enabled(self.user) is True

        # Disabled email notification
        user_attribute.enable_email_notification = False
        user_attribute.save()

        # Verify that email notifications are disabled for the user
        assert is_email_notification_enabled(self.user) is False

    def test_is_publisher_user(self):
        """
        Verify the function returns a boolean indicating if the user is part of any publisher app group.
        """
        assert not is_publisher_user(self.user)
        self.user.groups.add(factories.GroupFactory())
        assert is_publisher_user(self.user)
