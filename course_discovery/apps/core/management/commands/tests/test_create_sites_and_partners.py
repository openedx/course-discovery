import os

from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.models import Partner

SITES = ['dummy-site']


class CreateSitesAndPartnersTests(TestCase):
    """ Test the create_sites_and_partners command """

    def setUp(self):
        super().setUp()
        self.dns_name = "dummy-dns"
        self.theme_path = os.path.dirname(__file__)

    def _assert_site_and_partner_are_valid(self):
        """
        checks that all the sites and partners are valid.
        """
        sites = Site.objects.filter(domain__contains=self.dns_name)
        partners = Partner.objects.all()

        # there is an extra default site.
        self.assertEqual(len(sites), len(SITES))
        self.assertEqual(len(partners), len(SITES))

        for site in sites:
            if site.name in SITES:
                site_name = site.name
                self.assertEqual(
                    site.domain,
                    f"discovery-{site_name}-{self.dns_name}.example.com"
                )
                partner = Partner.objects.get(site=site)

                self.assertEqual(partner.short_code, site_name)
                self.assertEqual(partner.name, "dummy")
                self.assertEqual(
                    partner.courses_api_url,
                    f"https://dummy-{self.dns_name}.example.com/api/courses/v1/"
                )
                self.assertEqual(
                    partner.ecommerce_api_url,
                    f"https://ecommerce-dummy-{self.dns_name}.example.com/"
                )
                self.assertEqual(
                    partner.organizations_api_url,
                    "https://dummy-{dns_name}.example.com/api/organizations/v0/"
                )

    def test_missing_required_arguments(self):
        """
        Verify CommandError is raised when required arguments are missing.
        """

        # If a required argument is not specified the system should raise a CommandError
        with self.assertRaises(CommandError):
            call_command(
                "create_sites_and_partners",
                "--dns-name", self.dns_name,
            )

        with self.assertRaises(CommandError):
            call_command(
                "create_sites_and_partners",
                "--theme-path", self.theme_path,
            )

    def test_create_devstack_site_and_partner(self):
        """
        Verify that command creates sites and Partners for devstack
        """
        call_command(
            "create_sites_and_partners",
            "--dns-name", self.dns_name,
            "--theme-path", self.theme_path,
            "--devstack"
        )
        self._assert_site_and_partner_are_valid()

    def test_create_site_and_partner(self):
        """
        Verify that command creates sites and Partners
        """
        call_command(
            "create_sites_and_partners",
            "--dns-name", self.dns_name,
            "--theme-path", self.theme_path
        )
        self._assert_site_and_partner_are_valid()

        call_command(
            "create_sites_and_partners",
            "--dns-name", self.dns_name,
            "--theme-path", self.theme_path
        )
        # if we run command with same dns then it will not duplicates the sites and partners.
        self._assert_site_and_partner_are_valid()

        self.dns_name = "new-dns"
        call_command(
            "create_sites_and_partners",
            "--dns-name", self.dns_name,
            "--theme-path", self.theme_path
        )
        # if we run command with new dns then it should still create sites and partners without breaking.
        self._assert_site_and_partner_are_valid()
