# pylint: disable=no-member
from unittest.mock import patch

from django.test import TestCase

from course_discovery.apps.course_metadata.models import ProgramType
from course_discovery.apps.course_metadata.tests import factories, toggle_switch

MARKETING_SITE_PUBLISHERS_MODULE = 'course_discovery.apps.course_metadata.publishers.MarketingSitePublisher'


@patch(MARKETING_SITE_PUBLISHERS_MODULE + '.delete_program')
class SignalsTest(TestCase):
    def setUp(self):
        super(SignalsTest, self).setUp()
        self.program = factories.ProgramFactory(type=ProgramType.objects.get(name='MicroMasters'))

    def test_delete_program_signal_no_publish(self, delete_program_mock):
        toggle_switch('publish_program_to_marketing_site', False)
        self.program.delete()
        self.assertFalse(delete_program_mock.called)

    def test_delete_program_signal_with_publish(self, delete_program_mock):
        toggle_switch('publish_program_to_marketing_site', True)
        self.program.delete()
        delete_program_mock.assert_called_once_with(self.program)
