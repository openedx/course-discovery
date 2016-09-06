from unittest.mock import patch

from django.test import TestCase

from course_discovery.apps.course_metadata.tests import factories, toggle_switch


# pylint: disable=no-member


class SignalsTest(TestCase):
    def setUp(self):
        super(SignalsTest, self).setUp()
        self.program = factories.ProgramFactory()

    @patch('course_discovery.apps.course_metadata.publishers.MarketingSitePublisher.delete_program')
    def test_delete_program_signal_no_publish(self, delete_program_mock):
        self.program.delete()
        self.assertFalse(delete_program_mock.called)

    @patch('course_discovery.apps.course_metadata.publishers.MarketingSitePublisher.delete_program')
    def test_delete_program_signal_with_publish(self, delete_program_mock):
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.delete()
        delete_program_mock.assert_called_once_with(self.program)
        toggle_switch('publish_program_to_marketing_site', False)
