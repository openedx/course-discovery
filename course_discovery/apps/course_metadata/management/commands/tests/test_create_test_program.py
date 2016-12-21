from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import PartnerFactory, ProgramFactory


class CreateTestProgramCommandTests(TestCase):
    def test_create_command(self):
        call_command('create_test_program')
        # Verify that these objects have been created
        # If they have not they will throw a DoesNotExist error
        Partner.objects.get(name='test-partner')
        Program.objects.get(title='test-program')
        Program.objects.get(title='Test Digital Marketing Professional Certificate')

    def test_create_command_overwrite(self):
        # Verify that these objects can be overwritten
        PartnerFactory(name='test-partner', short_code='test')
        ProgramFactory(title='test-program', subtitle='test')
        ProgramFactory(title='Test Digital Marketing Professional Certificate', subtitle='test')
        call_command('create_test_program')
        partner = Partner.objects.get(name='test-partner')
        test_program = Program.objects.get(title='test-program')
        test_wharton_program = Program.objects.get(title='Test Digital Marketing Professional Certificate')
        self.assertNotEqual(partner.short_code, 'test')
        self.assertNotEqual(test_program.subtitle, 'test')
        self.assertNotEqual(test_wharton_program.subtitle, 'test')
