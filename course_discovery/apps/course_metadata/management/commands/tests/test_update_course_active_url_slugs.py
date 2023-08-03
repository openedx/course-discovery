import tempfile
from unittest.mock import patch

import mock
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase
from edx_toggles.toggles.testutils import override_waffle_switch
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.tests.factories import CourseFactory, MigrateCourseSlugConfigurationFactory
from course_discovery.apps.course_metadata.toggles import IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.update_course_active_url_slugs'


class UpdateCourseActiveUrlSlugCommandTests(TestCase):
    """
    Test suite for update_course_active_url_slug management command.
    """
    def setUp(self):
        super().setUp()
        self.course1_draft = CourseFactory(draft=True)
        self.course1_non_draft = CourseFactory(
            draft=False, draft_version_id=self.course1_draft.id, uuid=self.course1_draft.uuid
        )
        self.course2_draft = CourseFactory(draft=True)
        self.course2_non_draft = CourseFactory(
            draft=False, draft_version_id=self.course2_draft.id, uuid=self.course2_draft.uuid
        )
        self.course3_draft = CourseFactory(draft=True)
        self.course3_non_draft = CourseFactory(
            draft=False, draft_version_id=self.course3_draft.id, uuid=self.course3_draft.uuid
        )
        self.test_active_url_slugs = ['learn/python/python-programming-introduction',
                                      'learn/js/js-for-beginners', 'learn/cpp/cpp-crash-course']

        self.csv_header = 'course_uuid,course_url_slug\n'
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
        # add csv headers
        csv_file_content = self.csv_header
        courses_data = [
            (self.course1_draft.uuid, self.test_active_url_slugs[0]),
            (self.course2_draft.uuid, self.test_active_url_slugs[1]),
            (self.course3_draft.uuid, self.test_active_url_slugs[2]),
        ]

        for course_uuid, active_url_slug in courses_data:
            csv_file_content += ','.join([str(course_uuid), active_url_slug]) + '\n'

        return csv_file_content

    def test_missing_csv(self):
        """
        Test that the command raises CommandError if no csv is provided.
        """
        _ = MigrateCourseSlugConfigurationFactory.create(enabled=True)
        with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
            with self.assertRaises(CommandError):
                call_command('update_course_active_url_slugs')

    def test_invalid_csv_path(self):
        """
        Test that the command raises CommandError if an invalid csv path is provided.
        """
        with self.assertRaises(CommandError):
            call_command(
                'update_course_active_url_slugs', '--csv_file', 'no_csv'
            )

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_success_flow__through_configuration_model(self, mock_send_email_for_slug_updates):
        """
        Test that the command updates the active_url_slug for the courses in the csv file through the
        MigrateCourseSlugConfiguration model.
        """
        config = MigrateCourseSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)
        csv_file_name = config.csv_file.name
        excepted_csv_file = 'course_uuid,old_url_slug,new_url_slug,error_msg\n'
        excepted_csv_file += ','.join([str(self.course1_draft.uuid), self.course1_draft.active_url_slug,
                                       self.test_active_url_slugs[0], 'None']) + '\n'
        excepted_csv_file += ','.join([str(self.course2_draft.uuid), self.course2_draft.active_url_slug,
                                       self.test_active_url_slugs[1], 'None']) + '\n'
        excepted_csv_file += ','.join([str(self.course3_draft.uuid), self.course3_draft.active_url_slug,
                                       self.test_active_url_slugs[2], 'None']) + '\n'

        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course1 = self.course1_draft.active_url_slug
            current_slug_course2 = self.course2_draft.active_url_slug
            current_slug_course3 = self.course3_draft.active_url_slug
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_course_active_url_slugs'
                )

            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Reading csv file from config MigrateCourseSlugConfiguration {csv_file_name}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated the course url slug of course:{self.course1_draft.uuid} '
                    f'from {current_slug_course1} to {self.test_active_url_slugs[0]}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated the course url slug of course:{self.course2_draft.uuid} '
                    f'from {current_slug_course2} to {self.test_active_url_slugs[1]}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Updated the course url slug of course:{self.course3_draft.uuid} '
                    f'from {current_slug_course3} to {self.test_active_url_slugs[2]}'
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f'Course url slug update report in csv format:\n {excepted_csv_file}'
                ),
            )

        assert mock_send_email_for_slug_updates.call_count == 1

        self.assertEqual(self.course1_draft.active_url_slug, self.test_active_url_slugs[0])
        self.assertEqual(self.course1_non_draft.active_url_slug, self.test_active_url_slugs[0])
        self.assertEqual(self.course2_draft.active_url_slug, self.test_active_url_slugs[1])
        self.assertEqual(self.course2_non_draft.active_url_slug, self.test_active_url_slugs[1])
        self.assertEqual(self.course3_draft.active_url_slug, self.test_active_url_slugs[2])
        self.assertEqual(self.course3_non_draft.active_url_slug, self.test_active_url_slugs[2])

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_success_flow__through_csv_file_path(self, mock_send_email_for_slug_updates):
        """
        Test that the command updates the active_url_slug for the courses in the csv file through the
        csv file path.
        """
        with tempfile.NamedTemporaryFile(suffix='.csv') as csv_file:
            csv_file.write(self.csv_file_content.encode('utf-8'))
            csv_file.seek(0)

            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_course_active_url_slugs', '--csv_file', csv_file.name
                )

            self.assertEqual(self.course1_draft.active_url_slug, self.test_active_url_slugs[0])
            self.assertEqual(self.course1_non_draft.active_url_slug, self.test_active_url_slugs[0])
            self.assertEqual(self.course2_draft.active_url_slug, self.test_active_url_slugs[1])
            self.assertEqual(self.course2_non_draft.active_url_slug, self.test_active_url_slugs[1])
            self.assertEqual(self.course3_draft.active_url_slug, self.test_active_url_slugs[2])
            self.assertEqual(self.course3_non_draft.active_url_slug, self.test_active_url_slugs[2])

            assert mock_send_email_for_slug_updates.call_count == 1

    @mock.patch(LOGGER_PATH + '.send_email_for_slug_updates')
    def test_invalid_course_uuid(self, mock_send_email_for_slug_updates):
        """
        Test that the command logs error if an invalid course uuid is provided.
        """
        self.csv_file_content = self.csv_header
        self.csv_file_content += 'invalid-course-uuid,invalid-course-url-slug\n'

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

        _ = MigrateCourseSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)

        with patch(LOGGER_PATH + '.logger.error') as mock_logger:
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_course_active_url_slugs'
                )
            mock_logger.assert_has_calls([
                mock.call('Invalid course uuid: invalid-course-uuid'),
            ])
            # Assert that the email is sent and assert the email content
            assert mock_send_email_for_slug_updates.call_count == 1
            mock_send_email_for_slug_updates.assert_called_with(
                stats=(
                    'course_uuid,old_url_slug,new_url_slug,error_msg\n' +
                    'invalid-course-uuid,None,None,Invalid course uuid: invalid-course-uuid\n'
                ),
                to_users=settings.NOTIFY_SLUG_UPDATE_RECIPIENTS,
                subject='Course URL Slugs Update Report',
            )

    def test_invalid_course_url_slug(self):
        """
        Test that the command log error if an invalid course url slug is provided.
        """
        self.csv_file_content = self.csv_header
        self.csv_file_content += f'{self.course3_draft.uuid},\n'
        self.csv_file_content += f'{self.course2_draft.uuid},invalid-course-url-slug\n'

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

        _ = MigrateCourseSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)

        with patch(LOGGER_PATH + '.logger.error') as mock_logger:
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_course_active_url_slugs'
                )
            mock_logger.assert_has_calls([
                mock.call('Invalid course url slug: '),  # empty course url slug
                mock.call('Invalid course url slug: invalid-course-url-slug'),
            ])

    def test_valid_course_uuid_not_existing_in_db(self):
        """
        Test that the command logs error if a valid course uuid is provided but does not exist in the db.
        """
        # update the csv file content with an invalid course uuid
        course3_uuid = self.course3_non_draft.uuid
        self.csv_file_content = self.csv_header
        self.csv_file_content += f'{course3_uuid},{self.test_active_url_slugs[2]}\n'
        self.course3_draft.delete()

        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

        _ = MigrateCourseSlugConfigurationFactory.create(csv_file=self.csv_file, enabled=True)

        with patch(LOGGER_PATH + '.logger.error') as mock_logger:
            with override_waffle_switch(IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED, active=True):
                call_command(
                    'update_course_active_url_slugs'
                )
            mock_logger.assert_has_calls([
                mock.call(f'Course with uuid: {course3_uuid} does not exist'),
            ])
