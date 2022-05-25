""" Command to add logo, certificate logo, and banner image to an organization """
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import Organization


class Command(BaseCommand):
    """
    Uploads given images to an organization. This command is meant to be run
    from a provisioning script and not by hand.
    """

    def add_arguments(self, parser):
        parser.add_argument("--partner", default="edx")
        parser.add_argument("--logo")
        parser.add_argument("--certificate_logo")
        parser.add_argument("--banner_image")

    def handle(self, *args, **kwargs):
        partner_name = kwargs.get("partner")

        try:
            # We search by partner here because right now, the default provisioned
            # org does not have a name, but has "edx" as the partner
            organization = Organization.objects.filter(
                partner__short_code=partner_name
            )[:1].get()
            assets = self._open_assets(
                logo=kwargs.get("logo"),
                certificate_logo=kwargs.get("certificate_logo"),
                banner_image=kwargs.get("banner_image"),
            )
            organization.logo_image = assets["logo"]
            organization.certificate_logo_image = assets["certificate_logo"]
            organization.banner_image = assets["banner_image"]
            organization.save()
            self._cleanup(**assets)

        except Organization.DoesNotExist as no_organization_exists:
            raise CommandError from no_organization_exists

    def _open_assets(self, **kwargs):
        assets = {}
        for key, value in kwargs.items():
            try:
                assets[key] = File(open(value, "rb"))  # lint-amnesty, pylint: disable=consider-using-with
            except OSError as cannot_open_file:
                raise CommandError from cannot_open_file
        return assets

    def _cleanup(self, **kwargs):
        for _, value in kwargs.items():
            try:
                value.close()
            except OSError as error_while_closing:
                raise CommandError from error_while_closing
