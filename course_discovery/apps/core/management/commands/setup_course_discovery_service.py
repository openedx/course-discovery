""" Management command to set up course discovery service locally"""

from course_discovery.apps.core.models import Partner
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Set up course discovery service locally'
    domain_name = 'edx.devstack.lms:18381'

    def setup_course_discovery_service(self):
        site, _ = Site.objects.get_or_create(name=self.domain_name, domain=self.domain_name)
        Partner.objects.get_or_create(
            name='edx.devstack.lms:18381', short_code='edly',
            lms_url='http://edx.devstack.lms:18000', site=site,
            courses_api_url='http://edx.devstack.lms:18000/api/courses/v1/',
            ecommerce_api_url='http://edx.devstack.lms:18130/api/v2/',
            marketing_site_url_root='http://wordpress.edx.devstack.lms/',
            marketing_site_api_url='http://wordpress.edx.devstack.lms/wp-json/edly/v1/course_runs',
            studio_url='http://edx.devstack.lms:18010'
        )

    def handle(self, *args, **options):
        """Set up course discovery service locally."""
        self.setup_course_discovery_service()
