""" Tests publisher.utils"""
from django.contrib.auth.models import Group
from django.test import TestCase

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher.utils import is_email_notification_enabled, is_global_admin


class PublisherUtilsTests(TestCase):
    """ Tests for the publisher utils. """

    def setUp(self):
        super(PublisherUtilsTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)

    def test_email_notification_enabled_by_default(self):
        """ Test email notification is enabled for the user by default."""

        self.assertFalse(hasattr(self.user, 'attributes'))

        # Verify email notifications are enabled for user without associated attributes
        self.assertEqual(is_email_notification_enabled(self.user), True)

    def test_is_email_notification_enabled(self):
        """ Test email notification enabled/disabled for the user."""

        user_attribute = factories.UserAttributeFactory(user=self.user)

        # Verify email notifications are enabled for user with associated attributes,
        # but no explicit value set for the enable_email_notification attribute
        self.assertEqual(is_email_notification_enabled(self.user), True)

        # Disabled email notification
        user_attribute.enable_email_notification = False
        user_attribute.save()  # pylint: disable=no-member

        # Verify that email notifications are disabled for the user
        self.assertEqual(is_email_notification_enabled(self.user), False)

    def test_is_global_admin(self):
        """ Verify the function returns a boolean indicating if the user
        is a member of the administrative group.
        """
        self.assertFalse(self.user.groups.filter(name=ADMIN_GROUP_NAME).exists())
        self.assertFalse(is_global_admin(self.user))

        admin_group = Group.objects.get(name=ADMIN_GROUP_NAME)
        self.user.groups.add(admin_group)
        self.assertTrue(is_global_admin(self.user))
