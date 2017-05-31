from django.conf import settings
from django.contrib.sites.models import Site

from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory


class PartnerMixin(object):
    def setUp(self):
        super(PartnerMixin, self).setUp()
        Site.objects.all().delete()
        self.site = SiteFactory(id=settings.SITE_ID)
        self.partner = PartnerFactory(site=self.site)
