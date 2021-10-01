"""
Views for Edly Sites API.
"""
from django.contrib.sites.models import Site
from rest_framework import status, viewsets, filters
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.core.models import Partner
from edly_discovery_app.api.v1.constants import ERROR_MESSAGES
from edly_discovery_app.api.v1.helpers import validate_partner_configurations
from edly_discovery_app.api.v1.permissions import CanAccessSiteCreation


class EdlySiteViewSet(APIView):
    """
    Create Default Site and Partner Configuration.
    """
    permission_classes = [IsAuthenticated, CanAccessSiteCreation]

    def post(self, request):
        """
        POST /edly_api/v1/edly_sites/
        """

        validations_messages = validate_partner_configurations(request.data)
        if len(validations_messages) > 0:
            return Response(validations_messages, status=status.HTTP_400_BAD_REQUEST)

        try:
            self.discovery_site_setup()
            return Response(
                {'success': ERROR_MESSAGES.get('CLIENT_SITES_SETUP_SUCCESS')},
                status=status.HTTP_200_OK
            )
        except TypeError:
            return Response(
                {'error': ERROR_MESSAGES.get('CLIENT_SITES_SETUP_FAILURE')},
                status=status.HTTP_400_BAD_REQUEST
            )

    def discovery_site_setup(self):
        """
        Discovery site setup with default partner configurations.
        """
        discovery_base = self.request.data.get('discovery_site', '')
        old_discovery_base = self.request.data.get('old_domain_values', {}).get('discovery_site', None)
        discovery_site, __ = Site.objects.update_or_create(
            domain=old_discovery_base,
            name=old_discovery_base,
            defaults={'domain': discovery_base, 'name': discovery_base},
        )
        return self.get_updated_site_partner(discovery_site)

    def get_updated_site_partner(self, discovery_site):
        """
        Get updated site partner based on request data.
        """
        protocol = self.request.data.get('protocol', 'https')
        lms_base = self.request.data.get('lms_site', '')
        wordpress_base = self.request.data.get('wordpress_site', '')
        partner, __ = Partner.objects.get_or_create(site=discovery_site)

        partner.name = self.request.data.get('partner_name', '')
        partner.short_code = self.request.data.get('partner_short_code', '')
        partner.lms_url = '{protocol}://{lms_domain}'.format(protocol=protocol, lms_domain=lms_base)
        partner.studio_url = '{protocol}://{cms_domain}'.format(
            protocol=protocol,
            cms_domain=self.request.data.get('cms_site', ''),
        )
        partner.courses_api_url = '{protocol}://{lms_domain}/api/courses/v1/'.format(
            protocol=protocol,
            lms_domain=lms_base,
        )
        partner.ecommerce_api_url = '{protocol}://{payments_domain}/api/v2/'.format(
            protocol=protocol,
            payments_domain=self.request.data.get('payments_site', ''),
        )
        partner.organizations_api_url = '{protocol}://{lms_domain}/api/organizations/v0/organizations/'.format(
            protocol=protocol,
            lms_domain=lms_base,
        )
        partner.marketing_site_url_root = '{protocol}://{wordpress_domain}/'.format(
            protocol=protocol,
            wordpress_domain=wordpress_base,
        )
        partner.marketing_site_api_url = '{protocol}://{wordpress_domain}/wp-json/edly/v1/course_runs'.format(
            protocol=protocol,
            wordpress_domain=wordpress_base,
        )
        partner.save()

        return partner
