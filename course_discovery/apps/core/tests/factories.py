from uuid import uuid4

import factory
from django.contrib.sites.models import Site

from course_discovery.apps.api.fields import StdImageSerializerField
from course_discovery.apps.core.models import Currency, Partner, SalesforceConfiguration, User
from course_discovery.apps.core.tests.utils import FuzzyUrlRoot
from course_discovery.apps.course_metadata.models import Collaborator

USER_PASSWORD = 'password'


def add_m2m_data(m2m_relation, data):
    """ Helper function to enable factories to easily associate many-to-many data with created objects. """
    if data:
        m2m_relation.add(*data)


class CollaboratorFactory(factory.django.DjangoModelFactory):
    name = factory.Faker('name')
    image = StdImageSerializerField()
    uuid = factory.LazyFunction(uuid4)

    class Meta:
        model = Collaborator


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    domain = factory.Sequence(lambda n: f'test-domain-{n}.fake')
    name = factory.Faker('name')


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Sequence(lambda n: 'user_%d' % n)
    password = factory.PostGenerationMethodCall('set_password', USER_PASSWORD)
    is_active = True
    is_superuser = False
    is_staff = False
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    full_name = factory.LazyAttribute(lambda user: ' '.join((user.first_name, user.last_name)))

    class Meta:
        model = User


class StaffUserFactory(UserFactory):
    is_staff = True


class PartnerFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f'test-partner-{n}')  # pylint: disable=unnecessary-lambda
    short_code = factory.Sequence(lambda n: f'test{n}')  # pylint: disable=unnecessary-lambda
    courses_api_url = f'{FuzzyUrlRoot().fuzz()}/api/courses/v1/'
    lms_coursemode_api_url = f'{FuzzyUrlRoot().fuzz()}/api/course_mode/v1/'
    ecommerce_api_url = f'{FuzzyUrlRoot().fuzz()}/api/v2/'
    organizations_api_url = f'{FuzzyUrlRoot().fuzz()}/api/organizations/v1/'
    programs_api_url = f'{FuzzyUrlRoot().fuzz()}/api/programs/v1/'
    marketing_site_api_url = f'{FuzzyUrlRoot().fuzz()}/api/courses/v1/'
    marketing_site_url_root = factory.Faker('url')
    marketing_site_api_username = factory.Faker('user_name')
    marketing_site_api_password = factory.Faker('password')
    analytics_url = factory.Faker('url')
    analytics_token = factory.Faker('sha256')
    lms_url = ''
    lms_admin_url = f'{FuzzyUrlRoot().fuzz()}/admin'
    site = factory.SubFactory(SiteFactory)
    studio_url = factory.Faker('url')
    publisher_url = factory.Faker('url')

    class Meta:
        model = Partner


class CurrencyFactory(factory.django.DjangoModelFactory):
    code = factory.fuzzy.FuzzyText(length=6)
    name = factory.fuzzy.FuzzyText()

    class Meta:
        model = Currency


class SalesforceConfigurationFactory(factory.django.DjangoModelFactory):
    username = factory.fuzzy.FuzzyText()
    password = factory.fuzzy.FuzzyText()
    organization_id = factory.fuzzy.FuzzyText()
    security_token = factory.fuzzy.FuzzyText()
    is_sandbox = True
    partner = factory.SubFactory(PartnerFactory)
    case_record_type_id = factory.fuzzy.FuzzyText()

    class Meta:
        model = SalesforceConfiguration
