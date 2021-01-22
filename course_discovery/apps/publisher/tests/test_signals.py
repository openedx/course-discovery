from django.contrib.auth.models import Permission
from django.test import TestCase

from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


class TestCreateOrganizations(TestCase):
    def test_create_organizations_added_permissions(self):
        # Make sure created organization automatically have people permissions
        organization = OrganizationExtensionFactory()
        target_permissions = Permission.objects.filter(
            codename__in=['add_person', 'change_person', 'delete_person']
        )
        for permission in target_permissions:
            assert organization.group.permissions.filter(codename=permission.codename).exists()
