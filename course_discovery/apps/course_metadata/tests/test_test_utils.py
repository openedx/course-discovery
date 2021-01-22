import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.utils import build_salesforce_exception


@ddt.ddt
class BuildSalesforceException(TestCase):
    @ddt.data('Organization', 'Course', 'CourseRun')
    def test_build_salesforce_exception(self, record_type):
        expected = 'The Partner of this {record_type} has a Salesforce Configuration, ' \
            'try using {record_type}FactoryNoSignals instead.'.format(record_type=record_type)

        assert build_salesforce_exception(record_type) == expected
