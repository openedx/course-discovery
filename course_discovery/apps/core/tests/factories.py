import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.core.models import User, Partner
from course_discovery.apps.core.tests.utils import FuzzyUrlRoot

USER_PASSWORD = 'password'


class UserFactory(factory.DjangoModelFactory):
    username = factory.Sequence(lambda n: 'user_%d' % n)
    password = factory.PostGenerationMethodCall('set_password', USER_PASSWORD)
    is_active = True
    is_superuser = False
    is_staff = False

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
    marketing_site_api_username = FuzzyText().fuzz()
    marketing_site_api_password = FuzzyText().fuzz()
    oidc_url_root = '{root}'.format(root=FuzzyUrlRoot().fuzz())
    oidc_key = FuzzyText().fuzz()
    oidc_secret = FuzzyText().fuzz()

    class Meta(object):
        model = Partner
