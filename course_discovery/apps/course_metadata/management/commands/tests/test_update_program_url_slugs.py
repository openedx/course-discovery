import tempfile
import uuid

import ddt
import mock
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase
from edx_toggles.toggles.testutils import override_waffle_switch
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.tests.factories import MigrateProgramSlugConfigurationFactory, ProgramFactory
from course_discovery.apps.course_metadata.toggles import IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.update_program_url_slugs'


@ddt.ddt
class UpdateProgramUrlSlugCommandTests(TestCase):
    """
    Test suite for update_program_url_slug management command.
    """
    def setUp(self):
        super().setUp()
        self.program1 = ProgramFactory()
        self.program2 = ProgramFactory()
        self.program3 = ProgramFactory()

        self.test_active_url_slugs = ['category/subcategory/program-1',
                                      'category/subcategory/program-2', 'category/subcategory/program-3']

        self.csv_header = 'uuid,new_url_slug\n'
        self.csv_file_content = self.write_csv_file_content()

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

    def write_csv_file_content(self):
        """
        Write the csv file content to a file.
        """
        csv_file_content = self.csv_header
        program_data = [
            (self.program1.uuid, self.test_active_url_slugs[0]),
            (self.program2.uuid, self.test_active_url_slugs[1]),
            (self.program3.uuid, self.test_active_url_slugs[2]),
        ]

        for program_uuid, active_url_slug in program_data:
            csv_file_content += ','.join([str(program_uuid), active_url_slug]) + '\n'

        return csv_file_content

    def test_missing_csv(self):
        """
        Test that the command raises CommandError if no csv is provided.
        """
        _ = MigrateProgramSlugConfigurationFactory.create(enabled=True)
        with self.assertRaises(CommandError):
            call_command('update_program_url_slugs')

    def test_invalid_csv_path(self):
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaises(CommandError):
            call_command(
                'update_program_url_slugs', '--csv_from_config', 'no_csv'
            )

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_success_flow__through_configuration_model(self, mock_send_email_for_slug_updates):
        """
        Test that the command updates the marketing_slug for the programs in the csv file through the
        MigrateProgramSlugConfiguration model.
        """
        MigrateProgramSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)
        excepted_csv_file = 'uuid,new_url_slug\n'
        excepted_csv_file += ','.join([str(self.program1.uuid), self.test_active_url_slugs[0]]) + '\n'
        excepted_csv_file += ','.join([str(self.program2.uuid), self.test_active_url_slugs[1]]) + '\n'
        excepted_csv_file += ','.join([str(self.program3.uuid), self.test_active_url_slugs[2]]) + '\n'

        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_program1 = self.program1.marketing_slug
            current_slug_program2 = self.program2.marketing_slug
            current_slug_program3 = self.program3.marketing_slug

            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_program_url_slugs', args_from_database=True
                )

            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    'Initiating Program URL slug updation flow.'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated Program ({self.program1.uuid}) with slug: {current_slug_program1} '
                    f'to new url slug: {self.test_active_url_slugs[0]}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated Program ({self.program2.uuid}) with slug: {current_slug_program2} '
                    f'to new url slug: {self.test_active_url_slugs[1]}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated Program ({self.program3.uuid}) with slug: {current_slug_program3} '
                    f'to new url slug: {self.test_active_url_slugs[2]}'
                ),
            )

            assert mock_send_email_for_slug_updates.call_count == 1
            self.program1.refresh_from_db()
            self.program2.refresh_from_db()
            self.program3.refresh_from_db()
            assert self.program1.marketing_slug == self.test_active_url_slugs[0]
            assert self.program2.marketing_slug == self.test_active_url_slugs[1]
            assert self.program3.marketing_slug == self.test_active_url_slugs[2]
            expected_msg = f'program_uuid,old_slug,new_slug,error\n{self.program1.uuid},{current_slug_program1},' \
                           f'{self.test_active_url_slugs[0]},None\n{self.program2.uuid},{current_slug_program2},' \
                           f'{self.test_active_url_slugs[1]},None\n{self.program3.uuid},{current_slug_program3},' \
                           f'{self.test_active_url_slugs[2]},None\n'

            mock_send_email_for_slug_updates.assert_called_with(
                expected_msg,
                settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
                'Migrate Program Slugs Summary Report',
            )

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_success_flow__through_csv_file_path(self, mock_send_email_for_slug_updates):
        """
        Test that the command updates the marketing_slug for the programs in the csv file through the
        csv file path.
        """
        with tempfile.NamedTemporaryFile(suffix='.csv') as csv_file:
            csv_file.write(self.csv_file_content.encode('utf-8'))
            csv_file.seek(0)

            with LogCapture(LOGGER_PATH) as log_capture:
                current_slug_program1 = self.program1.marketing_slug
                current_slug_program2 = self.program2.marketing_slug
                current_slug_program3 = self.program3.marketing_slug
                with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                    call_command(
                        'update_program_url_slugs', '--csv_file', csv_file.name
                    )

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Initiating Program URL slug updation flow.'
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        f'Updated Program ({self.program1.uuid}) with slug: {current_slug_program1} '
                        f'to new url slug: {self.test_active_url_slugs[0]}'
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        f'Updated Program ({self.program2.uuid}) with slug: {current_slug_program2} '
                        f'to new url slug: {self.test_active_url_slugs[1]}'
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        f'Updated Program ({self.program3.uuid}) with slug: {current_slug_program3} '
                        f'to new url slug: {self.test_active_url_slugs[2]}'
                    ),
                )

            assert mock_send_email_for_slug_updates.call_count == 1
            expected_msg = f'program_uuid,old_slug,new_slug,error\n{self.program1.uuid},{current_slug_program1},' \
                           f'{self.test_active_url_slugs[0]},None\n{self.program2.uuid},{current_slug_program2},' \
                           f'{self.test_active_url_slugs[1]},None\n{self.program3.uuid},{current_slug_program3},' \
                           f'{self.test_active_url_slugs[2]},None\n'

            mock_send_email_for_slug_updates.assert_called_with(
                expected_msg,
                settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
                'Migrate Program Slugs Summary Report',
            )

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_invalid_program_uuid(self, mock_send_email_for_slug_updates):
        """
        Test that the command logs error if an invalid program uuid is provided.
        """
        self.csv_file_content = self.csv_header
        self.csv_file_content += 'invalid-program-uuid,invalid-program-url-slug\n'

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

        _ = MigrateProgramSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
            call_command(
                'update_program_url_slugs', args_from_database=True
            )

        assert mock_send_email_for_slug_updates.call_count == 1
        expected_msg = 'program_uuid,old_slug,new_slug,error\ninvalid-program-uuid,None,None,' \
                       'Skipping uuid invalid-program-uuid because of incorrect slug format\n'

        mock_send_email_for_slug_updates.assert_called_with(
            expected_msg,
            settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
            'Migrate Program Slugs Summary Report',
        )

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_valid_program_uuid_not_existing_in_db(self, mock_send_email_for_slug_updates):
        """
        Test that the command logs error if a valid program uuid is provided but does not exist in the db.
        """
        # update the csv file content with an invalid program uuid
        program_uuid = str(uuid.uuid4())
        self.csv_file_content = self.csv_header
        self.csv_file_content += f'{program_uuid},{self.test_active_url_slugs[2]}\n'

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

        _ = MigrateProgramSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
            with LogCapture(LOGGER_PATH) as log_capture:
                call_command(
                    'update_program_url_slugs', args_from_database=True
                )
                expected_msg = f'Unable to locate Program instance with code {program_uuid}'

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Initiating Program URL slug updation flow.'
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        expected_msg
                    ),
                )
                assert mock_send_email_for_slug_updates.call_count == 1
                expected_csv_msg = f'program_uuid,old_slug,new_slug,error\n{program_uuid},None,None,' \
                                   f'Unable to locate Program instance with code {program_uuid}\n'

                mock_send_email_for_slug_updates.assert_called_with(
                    expected_csv_msg,
                    settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
                    'Migrate Program Slugs Summary Report',
                )

    @ddt.data(
        ('test-slug-program-1', False),
        ('category/sub-category/campus-name-course-name', True),
    )
    @ddt.unpack
    def test_success_flow_with_flag_toggle(self, slug, state):
        """
        Test that the command updates the marketing_slug for the programs according to two different formats
        depending upon the subdirectory flag.
        """
        self.csv_file_content = self.csv_header
        self.csv_file_content += f'{self.program1.uuid},{slug}\n'

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        MigrateProgramSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)

        with mock.patch(LOGGER_PATH + '.send_email_for_slug_updates') as mock_send_email_for_slug_updates:
            with LogCapture(LOGGER_PATH) as log_capture:
                current_slug_program1 = self.program1.marketing_slug

                with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=state):
                    call_command(
                        'update_program_url_slugs', args_from_database=True
                    )

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Initiating Program URL slug updation flow.'
                    ),
                    (
                        LOGGER_PATH,
                        'INFO',
                        f'Updated Program ({self.program1.uuid}) with slug: {current_slug_program1} '
                        f'to new url slug: {slug}'
                    ),
                )

                assert mock_send_email_for_slug_updates.call_count == 1
                self.program1.refresh_from_db()
                assert self.program1.marketing_slug == slug
                expected_msg = f'program_uuid,old_slug,new_slug,error\n{self.program1.uuid},{current_slug_program1},' \
                               f'{slug},None\n'

                mock_send_email_for_slug_updates.assert_called_with(
                    expected_msg,
                    settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
                    'Migrate Program Slugs Summary Report',
                )
