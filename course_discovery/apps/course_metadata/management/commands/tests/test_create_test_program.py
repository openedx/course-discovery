from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import PartnerFactory, ProgramFactory


class CreateTestProgramCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory()
        self.command_args = [f'--partner_code={self.partner.short_code}']

    def test_create_command(self):
        call_command('create_test_program', *self.command_args)
        # Verify that the program has been created
        # If they have not they will throw a DoesNotExist error
        Program.objects.get(title='test-program')

    def test_create_command_overwrite(self):
        # Verify that the program can be overwritten
        ProgramFactory(title='test-program', subtitle='test')
        call_command('create_test_program', *self.command_args)
        test_program = Program.objects.get(title='test-program')
        self.assertNotEqual(test_program.subtitle, 'test')
