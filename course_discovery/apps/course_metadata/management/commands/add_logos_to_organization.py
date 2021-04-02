""" Command to add logo, certificate logo, and banner image to an organization """
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Organization


class Command(BaseCommand):
    """
    Uploads given images to an organization. This command is meant to be run
    from a provisioning script and not by hand.
    """
    def add_arguments(self, parser):
        parser.add_argument('--partner', default='edX')
        parser.add_argument('--logo', default='/edx/app/discovery/discovery/provision-temp/assets/demo-asset-logo.png')
        parser.add_argument('--certificate_logo', default='/edx/app/discovery/discovery/provision-temp/assets/demo-asset-certificate-logo.png')
        parser.add_argument('--banner_image', default='/edx/app/discovery/discovery/provision-temp/assets/demo-asset-banner-image.png')

    def handle(self, *args, **kwargs):
        partner_name = kwargs.get('partner')
        logo_path = kwargs.get("logo")
        certificate_logo_path = kwargs.get('certificate_logo')
        banner_image_path = kwargs.get('banner_image')
        try:
            organization = Organization.objects.get(partner=self._get_partner_by_name(partner_name))
            logo = File(open(logo_path, 'rb'))
            certificate_logo = File(open(certificate_logo_path, 'rb'))
            banner_image = File(open(banner_image_path, 'rb'))
            organization.logo_image = logo
            organization.certificate_logo_image = certificate_logo
            organization.banner_image = banner_image
            organization.save()
            logo.close()
            certificate_logo.close()
            banner_image.close()
        except (Organization.DoesNotExist, OSError) as e:
            print(CommandError(e))

    def _get_partner_by_name(self, partner_name):
        try:
            partner = Partner.objects.filter(name=partner_name)[:1].get()
            return partner
        except Partner.DoesNotExist:
            raise CommandError(f"Partner {partner_name} does not exist or could not be found.")

