"""
Tests for various celery tasks.
"""
from unittest import mock

import ddt
import pytest
from django.conf import settings
from django.db.models.signals import post_save
from django.test import TestCase, TransactionTestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.course_metadata.choices import BulkOperationStatus, BulkOperationType
from course_discovery.apps.course_metadata.models import BulkOperationTask, CourseType, Organization, ProgramType
from course_discovery.apps.course_metadata.signals import (
    on_bulk_operation_create, update_enterprise_inclusion_for_courses_and_programs
)
from course_discovery.apps.course_metadata.tasks import (
    process_bulk_operation, update_org_program_and_courses_ent_sub_inclusion
)
from course_discovery.apps.course_metadata.tests import factories


@ddt.ddt
class ProcessBulkOperationsTest(TransactionTestCase):
    """
    Unit Test suite for testing process_bulk_operations celery task.
    """
    def setUp(self):
        factories.PartnerFactory(short_code='test', id=settings.DEFAULT_PARTNER_ID)

    def test_create_queues_task(self):
        """
        Verify that creation of a BulkOperationTask queues a celery task for its processing
        """
        with mock.patch(
            'course_discovery.apps.course_metadata.signals.process_bulk_operation.apply_async'
        ) as mocked_apply_async:
            with mock.patch('course_discovery.apps.course_metadata.signals.uuid', return_value='123456-aaaa-bbbb'):
                bulk_operation_task = factories.BulkOperationTaskFactory()
                bulk_operation_task.refresh_from_db()
                mocked_apply_async.assert_called_with(
                    args=[bulk_operation_task.id], task_id=bulk_operation_task.task_id
                )
                bulk_operation_task.save()
                self.assertEqual(mocked_apply_async.call_count, 1)

    @ddt.data(
        ("CourseLoader", BulkOperationType.CourseCreate, True, {"success_count": 23, "failure_count": 2},
         BulkOperationStatus.Completed),
        ("CourseLoader", BulkOperationType.CourseCreate, False, None, BulkOperationStatus.Failed),
        ("CourseRunDataLoader", BulkOperationType.CourseRerun, True, {"success_count": 23, "failure_count": 2},
         BulkOperationStatus.Completed),
        ("CourseRunDataLoader", BulkOperationType.CourseRerun, False, None, BulkOperationStatus.Failed),
    )
    @ddt.unpack
    @mock.patch("course_discovery.apps.course_metadata.tasks.CourseLoader")
    @mock.patch("course_discovery.apps.course_metadata.tasks.CourseRunDataLoader")
    def test_bulk_operation_task_loader_execution(
            self, loader_class_name, task_type, should_succeed, expected_summary, expected_status,
            mock_course_run_loader, mock_course_loader
    ):
        post_save.disconnect(on_bulk_operation_create, sender=BulkOperationTask)
        mock_loader = mock_course_loader if loader_class_name == "CourseLoader" else mock_course_run_loader
        if should_succeed:
            mock_loader.return_value.ingest.return_value = expected_summary
        else:
            mock_loader.return_value.ingest.side_effect = KeyError("Simulated failure")

        bulk_operation_task = factories.BulkOperationTaskFactory(task_type=task_type)
        process_bulk_operation.apply_async(args=[bulk_operation_task.id])
        bulk_operation_task.refresh_from_db()

        mock_loader.assert_called_once()
        mock_loader.return_value.ingest.assert_called_once()
        self.assertEqual(bulk_operation_task.status, expected_status)
        self.assertEqual(bulk_operation_task.task_summary, expected_summary)

        post_save.connect(on_bulk_operation_create, sender=BulkOperationTask)


@pytest.mark.django_db
class EnterpriseSubscriptionInclusionTests(OAuth2Mixin, TestCase):
    """
    Test suite for update_org_program_and_courses_ent_sub_inclusion celery task.
    """
    def setUp(self):
        super().setUp()
        post_save.disconnect(update_enterprise_inclusion_for_courses_and_programs, sender=Organization)

    def tearDown(self):
        post_save.connect(update_enterprise_inclusion_for_courses_and_programs, Organization)
        super().tearDown()

    def test_org_enterprise_subscription_inclusion_toggle_course(self):
        """Test that toggling an org's enterprise_subscription_inclusion value will turn courses in the org on"""
        org = factories.OrganizationFactory(enterprise_subscription_inclusion=True)
        course_type = factories.CourseTypeFactory(slug=CourseType.VERIFIED_AUDIT)
        course = factories.CourseFactory(enterprise_subscription_inclusion=True, type=course_type)
        course.authoring_organizations.add(org)
        course.save()

        org.enterprise_subscription_inclusion = False
        org.save()

        update_org_program_and_courses_ent_sub_inclusion.apply_async(
            args=[org.id, org.enterprise_subscription_inclusion]
        )

        course.refresh_from_db()
        assert course.enterprise_subscription_inclusion is False

    def test_org_enterprise_subscription_inclusion_toggle_with_multiple_orgs(self):
        """
        Test that toggling an org's enterprise_subscription_inclusion value on will not turn the course, course run or
        program on if there is another org that is still off, with that course, course run and program
        """
        org = factories.OrganizationFactory(enterprise_subscription_inclusion=False)
        org2 = factories.OrganizationFactory(enterprise_subscription_inclusion=False)
        course = factories.CourseFactory(enterprise_subscription_inclusion=False)
        course_run = factories.CourseRunFactory(
            course=course,
            pacing_type='self_paced',
            enterprise_subscription_inclusion=False
        )
        program = factories.ProgramFactory(enterprise_subscription_inclusion=False)
        program.courses.add(course)
        program.save()

        course.authoring_organizations.add(org)
        course.authoring_organizations.add(org2)
        course.save()

        # Toggle one of the orgs to true
        org.enterprise_subscription_inclusion = True
        org.save()

        update_org_program_and_courses_ent_sub_inclusion.apply_async(
            args=[org.id, org.enterprise_subscription_inclusion])

        # Confirm that the course is still False
        course.refresh_from_db()
        assert course.enterprise_subscription_inclusion is False
        assert course_run.enterprise_subscription_inclusion is False
        assert program.enterprise_subscription_inclusion is False

    def test_org_enterprise_subscription_inclusion_toggle_courserun(self):
        """Test that toggling an org's enterprise_subscription_inclusion value will toggle the course run"""
        org = factories.OrganizationFactory(enterprise_subscription_inclusion=True)
        course_type = factories.CourseTypeFactory(slug=CourseType.VERIFIED_AUDIT)
        course = factories.CourseFactory(enterprise_subscription_inclusion=True, type=course_type)
        course_run = factories.CourseRunFactory(
            course=course,
            pacing_type='self_paced',
            enterprise_subscription_inclusion=True
        )

        course.authoring_organizations.add(org)
        course.save()

        org.enterprise_subscription_inclusion = False
        org.save()

        update_org_program_and_courses_ent_sub_inclusion.apply_async(
            args=[org.id, org.enterprise_subscription_inclusion])

        course_run.refresh_from_db()
        assert course_run.enterprise_subscription_inclusion is False

    def test_org_enterprise_subscription_inclusion_toggle_program(self):
        """Test that toggling an org's enterprise_subscription_inclusion value will toggle the program"""
        post_save.disconnect(update_enterprise_inclusion_for_courses_and_programs, sender=Organization)

        org = factories.OrganizationFactory(enterprise_subscription_inclusion=True)
        course_type = factories.CourseTypeFactory(slug=CourseType.VERIFIED_AUDIT)
        course = factories.CourseFactory(enterprise_subscription_inclusion=True, type=course_type)
        course.authoring_organizations.add(org)
        course.save()

        program_type = factories.ProgramTypeFactory(slug=ProgramType.XSERIES)
        program = factories.ProgramFactory(enterprise_subscription_inclusion=True, type=program_type)
        program.courses.add(course)
        program.save()

        org.enterprise_subscription_inclusion = False
        org.save()

        update_org_program_and_courses_ent_sub_inclusion.apply_async(
            args=[org.id, org.enterprise_subscription_inclusion])

        program.refresh_from_db()
        assert program.enterprise_subscription_inclusion is False
