"""
Unit tests for manage_program_subscription management command.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.models import ProgramSubscription, ProgramSubscriptionPrice
from course_discovery.apps.course_metadata.tests.factories import (
    ProgramFactory, ProgramSubscriptionConfigurationFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.manage_program_subscription'


class TestManageProgramSubscription(APITestCase):
    """
    Test suite for manage_program_subscription management command.
    """
    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create(username="test-user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        csv_file_content = ','.join(list(mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        self.program = ProgramFactory(uuid=mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT['uuid'], title='test-program')

    def test_subscription_created_and_updated(self):
        """
        Tests that the Program Subscription created if not exists, otherwise updated.
        """
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            subscription = ProgramSubscription.objects.get(program=self.program)
            subscription_price = ProgramSubscriptionPrice.objects.get(program_subscription=subscription)
            expected_log = 'Program located with slug: {}.Its subscription with price: {} USD is created'.format(
                self.program.marketing_slug, subscription_price.price
            )
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', expected_log)
            )

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            subscription = ProgramSubscription.objects.get(program=self.program)
            subscription_price = ProgramSubscriptionPrice.objects.get(program_subscription=subscription)
            expected_log = 'Program located with slug: {}.Its subscription with price: {} USD is updated'.format(
                self.program.marketing_slug, subscription_price.price
            )
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', expected_log)
            )

    def test_subscription_updated_if_exists(self):
        """
        Test that the command raises CommandError if an program does not exist
        """
        csv_file_content = ','.join(list(mock_data.INVALID_PROGRAM_SUBSCRIPTION_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.INVALID_PROGRAM_SUBSCRIPTION_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            expected_log = 'Unable to locate Program instance with code {}'.format(
                mock_data.INVALID_PROGRAM_SUBSCRIPTION_DICT['uuid']
            )
            log_capture.check_present(
                (LOGGER_PATH, 'ERROR', expected_log)
            )
