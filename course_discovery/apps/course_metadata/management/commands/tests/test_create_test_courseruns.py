from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import CourseRun, Organization
from course_discovery.apps.course_metadata.tests.factories import PartnerFactory


class CreateTestProgramCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        self.command_args = [f'--partner_code={self.partner.short_code}']

    def test_create_command(self):
        course_run_count_before = CourseRun.objects.count()
        call_command('create_test_courseruns', *self.command_args)
        org = Organization.objects.get(partner=self.partner)
        course_run_count_after = CourseRun.objects.count()
        assert course_run_count_after > course_run_count_before
