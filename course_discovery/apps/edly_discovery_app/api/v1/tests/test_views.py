"""
Unit tests for Edly Site API views.
"""
import json
from unittest import TestCase
import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.test.client import Client, RequestFactory
from django.urls import reverse
from rest_framework import status

from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import (
    SiteFactory,
    UserFactory,
    PartnerFactory,
    USER_PASSWORD,
)
from edly_discovery_app.api.v1.constants import CLIENT_SITE_SETUP_FIELDS

pytestmark = pytest.mark.django_db


def get_request_object_with_partner_access(user=None, short_code=None, site=None):
    """
    Get request object with partner access.

    Arguments:
        user (User): Django User object
        short_code (String): Partner Short Code
        site (Site): Django Site object

    Returns:
        Request: WSGI Request object with partner access
    """
    request_site = SiteFactory() if not site else site
    PartnerFactory(short_code=short_code, site=request_site)
    request = RequestFactory().get('/')
    request.site = request_site

    if user:
        request.user = user

    return request


class EdlySiteViewSet(TestCase):
    """
    Unit tests for EdlySiteViewSet View.
    """

    def setUp(self):
        """
        Setup data for test cases.
        """
        self.user = UserFactory(username=settings.EDLY_PANEL_WORKER_USER)
        self.short_code = 'red'
        self.url = reverse('edly_discovery_app:v1:edly_sites')
        self.request = get_request_object_with_partner_access(self.user, short_code=self.short_code)
        self.client = Client(SERVER_NAME=self.request.site.domain)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.expected_request_data = {
            'protocol': 'http',
            'partner_name': 'Test',
            'partner_short_code': 'test',
            'lms_site': 'test.edx.devstack.lms:18000',
            'cms_site': 'test.edx.devstack.lms:18010',
            'discovery_site': 'test.edx.devstack.lms:18381',
            'payments_site': 'test.edx.devstack.lms:18130',
            'wordpress_site': 'test.wordpress.edx.devstack.lms',
        }
        self.old_domain = 'old.test.edx.devstack.lms:18381'
        self.old_domain_values = {'old_domain_values': {'discovery_site': self.old_domain}}

    def test_without_authentication(self):
        """
        Verify authentication is required when accessing the endpoint.
        """
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 401)

    def test_without_permission(self):
        """
        Verify permission is required when accessing the endpoint.
        """
        edly_panel_user = UserFactory()
        api_url = reverse('edly_discovery_app:v1:edly_sites')
        request = get_request_object_with_partner_access(edly_panel_user, short_code='test_org')

        client = Client(SERVER_NAME=request.site.domain)
        client.login(username=edly_panel_user.username, password=USER_PASSWORD)

        response = client.post(api_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_request_data_authentication(self):
        """
        Verify authentication for request data.
        """
        response = self.client.post(self.url)
        request_data_fields_validations = [*response.json().keys()]

        assert set(request_data_fields_validations) == set(CLIENT_SITE_SETUP_FIELDS)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_setup(self):
        """
        Verify authentication for request data.
        """
        response = self.client.post(self.url, data=self.expected_request_data)
        assert response.status_code == status.HTTP_200_OK

        discovery_site = Site.objects.get(
            domain=self.expected_request_data['discovery_site'],
            name=self.expected_request_data['discovery_site'],
        )
        partner = Partner.objects.get(site=discovery_site)
        assert discovery_site.domain == self.expected_request_data['discovery_site']
        assert partner.short_code == self.expected_request_data['partner_short_code']

    def test_site_domain_remains_unchanged(self):
        """
        Verify if site value is unchanged.
        """
        self.expected_request_data.update({'old_domain_values': {
            'discovery_site': 'test.edx.devstack.lms:18381',
        }})
        SiteFactory(
            domain=self.expected_request_data['discovery_site'],
            name=self.expected_request_data['discovery_site']
        )
        assert len(Site.objects.all()) == 3
        response = self.client.post(
            self.url,
            data=json.dumps(self.expected_request_data),
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(Site.objects.all()) == 3
        discovery_site = Site.objects.get(
            domain=self.expected_request_data['discovery_site'],
            name=self.expected_request_data['discovery_site'],
        )
        assert discovery_site.domain == self.expected_request_data['discovery_site']
        assert discovery_site.name == self.expected_request_data['discovery_site']
    
    def test_site_domain_changes(self):
        """
        Verify if old site's domain gets updated.
        """ 
        self.expected_request_data.update(self.old_domain_values)
        SiteFactory(domain=self.old_domain, name=self.old_domain)
        assert len(Site.objects.all()) == 3
        response = self.client.post(
            self.url,
            data=json.dumps(self.expected_request_data),
            content_type='application/json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(Site.objects.all()) == 3
        discovery_site = Site.objects.get(
            domain=self.expected_request_data['discovery_site'],
            name=self.expected_request_data['discovery_site'],
        )
        assert discovery_site.domain == self.expected_request_data['discovery_site']
        assert discovery_site.name == self.expected_request_data['discovery_site']
