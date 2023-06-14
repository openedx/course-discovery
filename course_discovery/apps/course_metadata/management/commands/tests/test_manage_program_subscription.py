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
            subscription_price = ProgramSubscriptionPrice.objects.get(
                program_subscription=subscription,
                currency='USD'
            )
            expected_log = f'Program ({self.program.uuid}) located with slug: ' \
                           f'{self.program.marketing_slug} is marked eligible for subscription ' \
                           f'and its price: {subscription_price.price} USD is created'
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', expected_log)
            )

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            subscription = ProgramSubscription.objects.get(program=self.program)
            subscription_price = ProgramSubscriptionPrice.objects.get(
                program_subscription=subscription,
                currency='USD'
            )
            expected_log = f'Program ({self.program.uuid}) located with slug: ' \
                           f'{self.program.marketing_slug} is marked eligible for subscription ' \
                           f'and its price: {subscription_price.price} USD is updated'
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
            expected_log = f'Unable to locate Program instance with code ' \
                           f'{mock_data.INVALID_PROGRAM_SUBSCRIPTION_DICT["uuid"]}'
            log_capture.check_present(
                (LOGGER_PATH, 'ERROR', expected_log)
            )

    def test_record_skipped_if_subscription_eligibility_is_invalid(self):
        """
        Test that the log would be captured in case the record is skipped.
        """
        csv_file_content = ','.join(list(mock_data.PROGRAM_WITH_INVALID_SUBSCRIPTION_ELIGIBILITY_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.PROGRAM_WITH_INVALID_SUBSCRIPTION_ELIGIBILITY_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            expected_log = f'Skipped record: {mock_data.PROGRAM_WITH_INVALID_SUBSCRIPTION_ELIGIBILITY_DICT["uuid"]} ' \
                           f'because of invalid subscription eligibility value'
            log_capture.check_present(
                (LOGGER_PATH, 'WARNING', expected_log)
            )

    def test_subscription_object_should_be_updated_if_created_earlier(self):
        """
        Test that the subscription object must be updated if created earlier in case of future update(s)
        """
        csv_file_content = ','.join(list(mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            subscription = ProgramSubscription.objects.get(program=self.program)
            subscription_price = ProgramSubscriptionPrice.objects.get(
                program_subscription=subscription,
                currency='USD'
            )
            assert len(ProgramSubscription.objects.all()) == 1
            expected_log = f'Program ({self.program.uuid}) located with slug: ' \
                           f'{self.program.marketing_slug} is marked eligible for subscription ' \
                           f'and its price: {subscription_price.price} USD is created'
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', expected_log)
            )

        mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT['subscription_eligible'] = 'FALSE'
        csv_file_content = ','.join(list(mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.VALID_PROGRAM_SUBSCRIPTION_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            subscription = ProgramSubscription.objects.get(program=self.program)
            subscription_price = ProgramSubscriptionPrice.objects.get(
                program_subscription=subscription,
                currency='USD'
            )
            assert len(ProgramSubscription.objects.all()) == 1
            expected_log = f'Program ({self.program.uuid}) located with slug: ' \
                           f'{self.program.marketing_slug} is marked ineligible for subscription ' \
                           f'and its price: {subscription_price.price} USD is updated'
            log_capture.check_present(
                (LOGGER_PATH, 'INFO', expected_log)
            )

    def test_record_skipped_if_currency_is_invalid(self):
        """
        Test that the log would be captured in case the record is skipped.
        """
        csv_file_content = ','.join(list(mock_data.PROGRAM_WITH_INVALID_CURRENCY_DICT)) + '\n'
        csv_file_content += ','.join(f'"{key}"' for key in list(
            mock_data.PROGRAM_WITH_INVALID_CURRENCY_DICT.values()))
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )
        _ = ProgramSubscriptionConfigurationFactory.create(enabled=True, csv_file=self.csv_file)

        with LogCapture(LOGGER_PATH) as log_capture:
            call_command('manage_program_subscription')
            expected_log = f'Could not find currency {mock_data.PROGRAM_WITH_INVALID_CURRENCY_DICT["currency"]} ' \
                           f'for program {mock_data.PROGRAM_WITH_INVALID_CURRENCY_DICT["uuid"]}'
            log_capture.check_present(
                (LOGGER_PATH, 'WARNING', expected_log)
            )
