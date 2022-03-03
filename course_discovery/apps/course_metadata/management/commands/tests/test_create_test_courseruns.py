from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun
from course_discovery.apps.course_metadata.tests.factories import PartnerFactory


class CreateTestCourseRunsCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        self.command_args = [f'--partner_code={self.partner.short_code}']

    def test_create_course_runs_command(self):
        course_run_count_before = CourseRun.objects.count()
        parnter_course_url_before = self.partner.courses_api_url
        partner_marketing_url_before = self.partner.marketing_site_url_root
        call_command('create_test_courseruns', *self.command_args)
        course_run_count_after = CourseRun.objects.count()
        # Check that new course runs were created
        assert course_run_count_after > course_run_count_before
        # Check that the course api and marketing URLs were updated
        self.partner.refresh_from_db()
        assert parnter_course_url_before != self.partner.courses_api_url
        assert partner_marketing_url_before != self.partner.marketing_site_url_root
