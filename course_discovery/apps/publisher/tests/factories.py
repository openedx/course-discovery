import factory
from django.contrib.auth.models import Group
from factory.fuzzy import FuzzyChoice, FuzzyText

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.publisher.choices import InternalUserRole
from course_discovery.apps.publisher.models import OrganizationExtension, OrganizationUserRole, UserAttributes


class GroupFactory(factory.django.DjangoModelFactory):
    name = FuzzyText()

    class Meta:
        model = Group


class UserAttributeFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)

    class Meta:
        model = UserAttributes


class OrganizationUserRoleFactory(factory.django.DjangoModelFactory):
    organization = factory.SubFactory(factories.OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = FuzzyChoice(InternalUserRole.values.keys())

    class Meta:
        model = OrganizationUserRole


class OrganizationExtensionFactory(factory.django.DjangoModelFactory):
    organization = factory.SubFactory(factories.OrganizationFactory)
    group = factory.SubFactory(GroupFactory)

    class Meta:
        model = OrganizationExtension
