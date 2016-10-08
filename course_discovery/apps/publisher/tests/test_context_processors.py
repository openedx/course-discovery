""" Publisher context processor tests. """

from django.test import TestCase, RequestFactory

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.context_processors import publisher
from course_discovery.apps.publisher.utils import is_email_notification_enabled


class PublisherContextProcessorTests(TestCase):
    """ Tests for publisher.context_processors.publisher """

    def test_publisher(self):
        request = RequestFactory().get('/')
        request.user = UserFactory()
        self.assertDictEqual(
            publisher(request), {'is_email_notification_enabled': is_email_notification_enabled(request.user)}
        )
