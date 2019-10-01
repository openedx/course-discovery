from django.conf import settings
from django.contrib.sites.models import Site
from django.test import RequestFactory

from conftest import TEST_DOMAIN
from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory


class SiteMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Site.objects.all().delete()
        cls.site = SiteFactory(id=settings.SITE_ID, domain=TEST_DOMAIN)
        cls.partner = PartnerFactory(site=cls.site)

        cls.request = RequestFactory(SERVER_NAME=cls.site.domain).get('')
        cls.request.site = cls.site

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.partner.delete()

    def setUp(self):
        super().setUp()
        self.client = self.client_class(SERVER_NAME=TEST_DOMAIN)
