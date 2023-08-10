from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import BulkModifyProgramHookConfig
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory


class ModifyProgramHooksCommandTest(TestCase):
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.modify_program_hooks.logger'

    def setUp(self):
        super().setUp()
        self.config = BulkModifyProgramHookConfig.get_solo()

    def testNormalRun(self):
        program = ProgramFactory()
        program1 = ProgramFactory()
        self.config.program_hooks = '''{uuid}:Bananas in pajamas
        {uuid1}:Are coming down the stairs'''.format(uuid=program.uuid, uuid1=program1.uuid)
        self.config.save()
        call_command('modify_program_hooks')
        program.refresh_from_db()
        program1.refresh_from_db()
        self.assertEqual(program.marketing_hook, 'Bananas in pajamas')
        self.assertEqual(program1.marketing_hook, 'Are coming down the stairs')

    def testWeirdCharactersInHookText(self):
        program = ProgramFactory()
        self.config.program_hooks = '%s:+:[{])(%%' % program.uuid
        self.config.save()
        call_command('modify_program_hooks')
        program.refresh_from_db()
        self.assertEqual(program.marketing_hook, '+:[{])(%')

    @mock.patch(LOGGER_PATH)
    def testBadUUID(self, mock_logger):
        self.config.program_hooks = 'not-a-UUID:bananas'
        self.config.save()
        call_command('modify_program_hooks')
        mock_logger.warning.assert_called_with('Incorrectly formatted uuid "not-a-UUID"')

    @mock.patch(LOGGER_PATH)
    def testProgramDoesntExist(self, mock_logger):
        program = ProgramFactory()
        uuid = program.uuid
        self.config.program_hooks = '%s:bananas' % uuid
        program.delete()
        self.config.save()
        call_command('modify_program_hooks')
        mock_logger.warning.assert_called_with(f'Cannot find program with uuid {uuid}')

    @mock.patch(LOGGER_PATH)
    def testUnreadableLine(self, mock_logger):
        self.config.program_hooks = 'NopeNopeNope'
        self.config.save()
        call_command('modify_program_hooks')
        mock_logger.warning.assert_called_with('Incorrectly formatted line NopeNopeNope')
