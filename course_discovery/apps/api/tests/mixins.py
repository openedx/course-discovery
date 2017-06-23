from django.test import RequestFactory

from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory


class SiteMixin(object):
    def setUp(self):
        super(SiteMixin, self).setUp()
        domain = 'testserver.fake'
        self.client = self.client_class(SERVER_NAME=domain)
        self.site = SiteFactory(domain=domain)
        self.partner = PartnerFactory(site=self.site)

        self.request = RequestFactory(SERVER_NAME=self.site.domain).get('')
        self.request.site = self.site
