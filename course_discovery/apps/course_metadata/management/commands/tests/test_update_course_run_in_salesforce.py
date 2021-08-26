from unittest import mock

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase
from simple_salesforce.exceptions import SalesforceResourceNotFound
from testfixtures import LogCapture

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.management.commands.update_course_run_in_salesforce import logger
from course_discovery.apps.course_metadata.models import Course, CourseRun, CourseRunType


class TestUpdateCourseRunInSalesforce(TestCase):
    def setUp(self):
        super().setUp()
        stored_site, created = Site.objects.get_or_create(  # pylint: disable=unused-variable
            domain='example.com'
        )
        self.partner = Partner.objects.create(
            site=stored_site,
            name='edX',
            short_code='edx'
        )
        self.salesforce_util_path = 'course_discovery.apps.course_metadata.utils.SalesforceUtil'
        self.run_key = 'course-v1:edX+DemoX+Demo_Course'

        course = Course.objects.create(partner=self.partner, key='test-org-course', title='Title')
        course_type = CourseRunType.objects.get(slug=CourseRunType.AUDIT)
        CourseRun.objects.create(course=course, key=self.run_key, type=course_type,
                                 status=CourseRunStatus.Published, salesforce_id='SomeSalesforceId')

    def test_update_course_run(self):
        """Test Cases: update course runs in the salesforce"""

        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            call_command('update_course_run_in_salesforce')
            mock_salesforce_util().update_course_run.assert_called()

    def test_update_course_run_resource_not_found(self):
        """Test Cases: update course runs logs resource not found error"""

        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            mock_salesforce_util().update_course_run.side_effect = SalesforceResourceNotFound('/test', 404, 'test', {})
            with LogCapture(logger.name) as log_capture:
                call_command('update_course_run_in_salesforce')
                log_capture.check(
                    (
                        logger.name,
                        'WARNING',
                        'Entity deleted from SalesForce [{}]'.format(self.run_key),
                    )
                )
