import pytest
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
    lms_coursemode_api_url = 'http://courses.fake.org/api/course_modes/v1/'
    ecommerce_api_url = 'https://ecommerce.fake.org/api/v1/courses/'
    organizations_api_url = 'https://orgs.fake.org/api/v1/organizations/'
    programs_api_url = 'https://programs.fake.org/api/v1/programs/'
    lms_url = 'http://courses.fake.org/'
    studio_url = 'http://studio.fake.org/'
    publisher_url = 'http://publisher.fake.org/'
    marketing_site_api_url = 'https://www.fake.org/api/v1/courses/'
    marketing_site_url_root = 'https://www.fake.org/'
    marketing_site_api_username = 'marketing-username'
    marketing_site_api_password = 'marketing-password'

    def _check_partner(self, partner):
        assert partner.site.domain == self.site_domain
        assert partner.short_code == self.partner_code
        assert partner.name == self.partner_name
        assert partner.courses_api_url == self.courses_api_url
        assert partner.ecommerce_api_url == self.ecommerce_api_url
        assert partner.lms_coursemode_api_url == self.lms_coursemode_api_url
        assert partner.lms_url == self.lms_url
        assert partner.studio_url == self.studio_url
        assert partner.publisher_url == self.publisher_url
        assert partner.organizations_api_url == self.organizations_api_url
        assert partner.programs_api_url == self.programs_api_url
        assert partner.marketing_site_api_url == self.marketing_site_api_url
        assert partner.marketing_site_url_root == self.marketing_site_url_root
        assert partner.marketing_site_api_username == self.marketing_site_api_username
        assert partner.marketing_site_api_password == self.marketing_site_api_password

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
            'lms_coursemode_api_url': 'lms-coursemode-api-url',
            'ecommerce_api_url': 'ecommerce-api-url',
            'organizations_api_url': 'organizations-api-url',
            'programs_api_url': 'programs-api-url',
            'lms_url': 'lms-url',
            'studio_url': 'studio-url',
            'publisher_url': 'publisher-url',
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
            lms_coursemode_api_url=self.lms_coursemode_api_url,
            ecommerce_api_url=self.ecommerce_api_url,
            organizations_api_url=self.organizations_api_url,
            programs_api_url=self.programs_api_url,
            lms_url=self.lms_url,
            studio_url=self.studio_url,
            publisher_url=self.publisher_url,
            marketing_site_api_url=self.marketing_site_api_url,
            marketing_site_url_root=self.marketing_site_url_root,
            marketing_site_api_username=self.marketing_site_api_username,
            marketing_site_api_password=self.marketing_site_api_password,
        )

    def test_create_partner(self):
        """ Verify the command creates a new Partner. """

        partners = Partner.objects.all()
        assert partners.count() == 0

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
        self.lms_coursemode_api_url = 'http://courses.updated.org/api/course_modes/v1/'
        self.ecommerce_api_url = 'https://ecommerce.updated.org/api/v1/courses/'
        self.organizations_api_url = 'https://orgs.updated.org/api/v1/organizations/'
        self.programs_api_url = 'https://programs.updated.org/api/v1/programs/'
        self.lms_url = 'http://courses.updated.org/'
        self.studio_url = 'http://studio.updated.org/'
        self.publisher_url = 'http://publisher.updated.org/'
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
            lms_coursemode_api_url=self.lms_coursemode_api_url,
            ecommerce_api_url=self.ecommerce_api_url,
            organizations_api_url=self.organizations_api_url,
            programs_api_url=self.programs_api_url,
            lms_url=self.lms_url,
            studio_url=self.studio_url,
            publisher_url=self.publisher_url,
            marketing_site_api_url=self.marketing_site_api_url,
            marketing_site_url_root=self.marketing_site_url_root,
            marketing_site_api_username=self.marketing_site_api_username,
            marketing_site_api_password=self.marketing_site_api_password,
        )

        partner = Partner.objects.get(short_code=self.partner_code)
        self._check_partner(partner)

        site.refresh_from_db()
        assert site.domain == self.site_domain
        assert partner.site == site

    @data(
        [''],
        ['--code="xyz"'],  # Raises error because 'name' is not provided
        ['--name="XYZ Partner"']  # Raises error because 'code' is not provided
    )
    def test_missing_required_arguments(self, command_args):
        """ Verify CommandError is raised when required arguments are missing """

        # If a required argument is not specified the system should raise a CommandError
        with pytest.raises(CommandError):
            call_command(self.command_name, *command_args)
