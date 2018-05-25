import datetime

import mock
from django.test import TestCase

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.tests import factories


class MockedStartEndDateTestCase(TestCase):
    def setUp(self):
        super(MockedStartEndDateTestCase, self).setUp()
        start_date_patcher = mock.patch(
            'course_discovery.apps.publisher.models.CourseRun.lms_start', new_callable=mock.PropertyMock
        )
        self.addCleanup(start_date_patcher.stop)
        self.start_date_mock = start_date_patcher.start()
        self.start_date_mock.return_value = datetime.datetime.utcnow()
        end_date_patcher = mock.patch(
            'course_discovery.apps.publisher.models.CourseRun.lms_end', new_callable=mock.PropertyMock
        )
        self.addCleanup(end_date_patcher.stop)
        self.end_date_mock = end_date_patcher.start()
        self.end_date_mock.return_value = datetime.datetime.utcnow()


def create_non_staff_user_and_login(test_class):
    """ Create non staff user and login and return user and group. """
    non_staff_user = UserFactory()
    group = factories.GroupFactory()

    test_class.client.logout()
    test_class.client.login(username=non_staff_user.username, password=USER_PASSWORD)

    return non_staff_user, group
