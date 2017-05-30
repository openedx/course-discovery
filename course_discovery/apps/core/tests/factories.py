import factory
from django.contrib.sites.models import Site

from course_discovery.apps.core.models import Partner, User
from course_discovery.apps.core.tests.utils import FuzzyUrlRoot


USER_PASSWORD = 'password'


class SiteFactory(factory.DjangoModelFactory):
    class Meta:
        model = Site

    domain = factory.Sequence(lambda n: 'test-domain-{number}.fake'.format(number=n))
    name = factory.Faker('name')


class UserFactory(factory.DjangoModelFactory):
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


class PartnerFactory(factory.DjangoModelFactory):
    name = factory.Sequence(lambda n: 'test-partner-{}'.format(n))  # pylint: disable=unnecessary-lambda
    short_code = factory.Sequence(lambda n: 'test{}'.format(n))  # pylint: disable=unnecessary-lambda
    courses_api_url = '{root}/api/courses/v1/'.format(root=FuzzyUrlRoot().fuzz())
    ecommerce_api_url = '{root}/api/courses/v1/'.format(root=FuzzyUrlRoot().fuzz())
    organizations_api_url = '{root}/api/organizations/v1/'.format(root=FuzzyUrlRoot().fuzz())
    programs_api_url = '{root}/api/programs/v1/'.format(root=FuzzyUrlRoot().fuzz())
    marketing_site_api_url = '{root}/api/courses/v1/'.format(root=FuzzyUrlRoot().fuzz())
    marketing_site_url_root = '{root}/'.format(root=FuzzyUrlRoot().fuzz())
    marketing_site_api_username = factory.Faker('user_name')
    marketing_site_api_password = factory.Faker('password')
    oidc_url_root = '{root}'.format(root=FuzzyUrlRoot().fuzz())
    oidc_key = factory.Faker('sha256')
    oidc_secret = factory.Faker('sha256')
    site = factory.SubFactory(SiteFactory)
    studio_url = FuzzyUrlRoot().fuzz()

    class Meta(object):
        model = Partner
