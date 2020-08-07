from ddt import data, ddt
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import SiteFactory


@ddt
class CreateOrUpdatePartnerCommandTests(TestCase):
    command_name = 'create_or_update_partner'

    site_domain = 'test.example.com'
    partner_code = 'abc'
    partner_name = 'ABC Partner'
    courses_api_url = 'https://courses.fake.org/api/v1/courses/'
    ecommerce_api_url = 'https://ecommerce.fake.org/api/v1/courses/'
    organizations_api_url = 'https://orgs.fake.org/api/v1/organizations/'
    programs_api_url = 'https://programs.fake.org/api/v1/programs/'
    marketing_site_api_url = 'https://www.fake.org/api/v1/courses/'
    marketing_site_url_root = 'https://www.fake.org/'
    marketing_site_api_username = 'marketing-username'
    marketing_site_api_password = 'marketing-password'

    def _check_partner(self, partner):
        self.assertEqual(partner.site.domain, self.site_domain)
        self.assertEqual(partner.short_code, self.partner_code)
        self.assertEqual(partner.name, self.partner_name)
        self.assertEqual(partner.courses_api_url, self.courses_api_url)
        self.assertEqual(partner.ecommerce_api_url, self.ecommerce_api_url)
        self.assertEqual(partner.organizations_api_url, self.organizations_api_url)
        self.assertEqual(partner.programs_api_url, self.programs_api_url)
        self.assertEqual(partner.marketing_site_api_url, self.marketing_site_api_url)
        self.assertEqual(partner.marketing_site_url_root, self.marketing_site_url_root)
        self.assertEqual(partner.marketing_site_api_username, self.marketing_site_api_username)
        self.assertEqual(partner.marketing_site_api_password, self.marketing_site_api_password)

    def _call_command(self, **kwargs):
        """
        Internal helper method for interacting with the create_or_update_partner management command
        """

        # Required arguments
        command_args = [
            '--code={partner_code}'.format(partner_code=kwargs['partner_code']),
        ]

        # Optional arguments
        arg_map = {
            'site_id': 'site-id',
            'site_domain': 'site-domain',
            'partner_name': 'name',
            'courses_api_url': 'courses-api-url',
            'ecommerce_api_url': 'ecommerce-api-url',
            'organizations_api_url': 'organizations-api-url',
            'programs_api_url': 'programs-api-url',
            'marketing_site_api_url': 'marketing-site-api-url',
            'marketing_site_url_root': 'marketing-site-url-root',
            'marketing_site_api_username': 'marketing-site-api-username',
            'marketing_site_api_password': 'marketing-site-api-password',
        }

        for kwarg, value in kwargs.items():
            if arg_map.get(kwarg):
                command_args.append('--{arg}={value}'.format(arg=arg_map[kwarg], value=value))

        call_command(self.command_name, *command_args)

    def _create_partner(self):
        """ Helper method to create a new partner """
        self._call_command(
            site_domain=self.site_domain,
            partner_code=self.partner_code,
            partner_name=self.partner_name,
            courses_api_url=self.courses_api_url,
            ecommerce_api_url=self.ecommerce_api_url,
            organizations_api_url=self.organizations_api_url,
            programs_api_url=self.programs_api_url,
            marketing_site_api_url=self.marketing_site_api_url,
            marketing_site_url_root=self.marketing_site_url_root,
            marketing_site_api_username=self.marketing_site_api_username,
            marketing_site_api_password=self.marketing_site_api_password,
        )

    def test_create_partner(self):
        """ Verify the command creates a new Partner. """

        partners = Partner.objects.all()
        self.assertEqual(partners.count(), 0)

        self._create_partner()

        partner = Partner.objects.get(short_code=self.partner_code)
        self._check_partner(partner)

    def test_update_partner(self):
        """ Verify the command updates an existing Partner """
        self._create_partner()

        site = SiteFactory()
        self.site_domain = 'some-other-test.example.org'

        self.partner_name = 'Updated Partner'
        self.courses_api_url = 'https://courses.updated.org/api/v1/courses/'
        self.ecommerce_api_url = 'https://ecommerce.updated.org/api/v1/courses/'
        self.organizations_api_url = 'https://orgs.updated.org/api/v1/organizations/'
        self.programs_api_url = 'https://programs.updated.org/api/v1/programs/'
        self.marketing_site_api_url = 'https://www.updated.org/api/v1/courses/'
        self.marketing_site_url_root = 'https://www.updated.org/'
        self.marketing_site_api_username = 'updated-username'
        self.marketing_site_api_password = 'updated-password'

        self._call_command(
            site_id=site.id,
            site_domain=self.site_domain,
            partner_code=self.partner_code,
            partner_name=self.partner_name,
            courses_api_url=self.courses_api_url,
            ecommerce_api_url=self.ecommerce_api_url,
            organizations_api_url=self.organizations_api_url,
            programs_api_url=self.programs_api_url,
            marketing_site_api_url=self.marketing_site_api_url,
            marketing_site_url_root=self.marketing_site_url_root,
            marketing_site_api_username=self.marketing_site_api_username,
            marketing_site_api_password=self.marketing_site_api_password,
        )

        partner = Partner.objects.get(short_code=self.partner_code)
        self._check_partner(partner)

        site.refresh_from_db()
        self.assertEqual(site.domain, self.site_domain)
        self.assertEqual(partner.site, site)

    @data(
        [''],
        ['--code="xyz"'],  # Raises error because 'name' is not provided
        ['--name="XYZ Partner"']  # Raises error because 'code' is not provided
    )
    def test_missing_required_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments are missing """

        # If a required argument is not specified the system should raise a CommandError
        with self.assertRaises(CommandError):
            call_command(self.command_name, *command_args)
