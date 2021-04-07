""" Tests for adding logos command """
from unittest import mock

import pytest
from django.core.files import File
from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.management.commands.add_logos_to_organization import Command
from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory, PartnerFactory


class AddLogosToOrganizationTest(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(short_code="testx")
        self.organization = OrganizationFactory(partner=self.partner, name="testx")
        self.logo = mock.MagicMock(spec=File, name="logo")
        self.logo.name = "logo"
        self.certificate_logo = mock.MagicMock(spec=File, name="certificate_logo")
        self.certificate_logo.name = "certificate_logo"
        self.banner_image = mock.MagicMock(spec=File, name="banner_image")
        self.banner_image.name = "banner image"

    def test_partner_not_found(self):
        with pytest.raises(Exception):
            call_command(Command())

    def test_image_paths_not_found(self):
        with pytest.raises(Exception):
            call_command(
                Command(),
                partner="testx",
            )

    @pytest.mark.django_db
    def test_two_organizations_with_same_partner_returns_correct_org(self):
        new_org = OrganizationFactory(partner=self.partner, name="notx")
        assert len(Organization.objects.all()) > 1
        self.organization.logo_image = None
        new_org.logo_image = None
        with mock.patch(
            "course_discovery.apps.course_metadata.management.commands.add_logos_to_organization.Command._open_assets",
            return_value={
                "logo": self.logo,
                "certificate_logo": self.certificate_logo,
                "banner_image": self.banner_image,
            },
        ):
            call_command(
                Command(),
                partner="testx",
                logo="/",
                certificate_logo="/",
                banner_image="/",
            )
            self.organization.refresh_from_db()
            assert "/media/organization/logos/" in self.organization.logo_image.path
