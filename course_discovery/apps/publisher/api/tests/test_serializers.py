from django.test import TestCase

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.api.serializers import GroupUserSerializer, OrganizationUserRoleSerializer
from course_discovery.apps.publisher.tests.factories import OrganizationUserRoleFactory


class GroupUserSerializerTests(TestCase):

    def test_data_with_full_name(self):
        """ Verify that UserSerializer serialize the user object. """

        user = UserFactory(full_name='Test User')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.full_name, 'email': user.email}
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_full_name(self):
        """ Verify that UserSerializer serialize the user object using username
        if full_name is not available.
        """

        user = UserFactory(full_name='', first_name='', last_name='')
        serializer = GroupUserSerializer(user)

        expected = {'id': user.id, 'full_name': user.username, 'email': user.email}
        self.assertDictEqual(serializer.data, expected)


class OrganizationUserRoleSerializerTests(TestCase):
    def test_basic_serialization(self):
        role = OrganizationUserRoleFactory()
        serializer = OrganizationUserRoleSerializer(role)

        expected = {'id': role.id, 'role': role.role, 'user': GroupUserSerializer(role.user).data}
        self.assertDictEqual(serializer.data, expected)
