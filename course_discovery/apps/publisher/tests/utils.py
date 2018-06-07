from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.tests import factories


def create_non_staff_user_and_login(test_class):
    """ Create non staff user and login and return user and group. """
    non_staff_user = UserFactory()
    group = factories.GroupFactory()

    test_class.client.logout()
    test_class.client.login(username=non_staff_user.username, password=USER_PASSWORD)

    return non_staff_user, group
