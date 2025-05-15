"""
Tests for various celery tasks.
"""
from unittest import mock

import ddt
import pytest
from django.conf import settings
from django.test import TransactionTestCase
from django_celery_results.models import TaskResult

from course_discovery.apps.course_metadata.choices import BulkOperationStatus, BulkOperationType
from course_discovery.apps.course_metadata.tests import factories


@ddt.ddt
class BulkOperationTaskTest(TransactionTestCase):
    """
    Unit Test class for testing Celery Tasks and their functionality.
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
        mock_loader = mock_course_loader if loader_class_name == "CourseLoader" else mock_course_run_loader
        if should_succeed:
            mock_loader.return_value.ingest.return_value = expected_summary
        else:
            mock_loader.return_value.ingest.side_effect = KeyError("Simulated failure")

        bulk_operation_task = factories.BulkOperationTaskFactory(task_type=task_type)
        bulk_operation_task.refresh_from_db()

        mock_loader.assert_called_once()
        mock_loader.return_value.ingest.assert_called_once()
        self.assertEqual(bulk_operation_task.status, expected_status)
        self.assertEqual(bulk_operation_task.task_summary, expected_summary)

    def test_bulk_operation_task_creation(self):
        """
        Verify that the bulk operation task is created with the correct attributes.
        """
        bulk_operation_task = factories.BulkOperationTaskFactory()
        assert bulk_operation_task.task_type == BulkOperationType.CourseCreate
        self.assertIsNotNone(bulk_operation_task.uploaded_by)
        self.assertTrue(bulk_operation_task.csv_file.name.endswith('.csv'))

    def test_task_result_property_with_existing_result(self):
        """
        Verify that the task_result method returns the correct TaskResult object
        """
        with mock.patch('course_discovery.apps.course_metadata.signals.uuid', return_value='test-task-123'):
            bulk_operation = factories.BulkOperationTaskFactory()
            task_result = TaskResult.objects.create(
                task_id="test-task-123",
                status="SUCCESS",
                result='{"message": "Task completed"}'
            )
        result = bulk_operation.task_result
        self.assertEqual(result, task_result)

    def test_task_result_property_with_no_task_result(self):
        """
        Verify that the task_result method handles if no task result is found.
        """
        bulk_operation = factories.BulkOperationTaskFactory(task_id="non-existent-task")
        self.assertIsNone(bulk_operation.task_result)

    def test_task_result_property_with_no_task_id(self):
        """
        Verify that the task_result method handles if no task ID is associated with the bulk operation.
        """
        bulk_operation = factories.BulkOperationTaskFactory(task_id=None)
        self.assertIsNone(bulk_operation.task_result)

    def test_str_representation(self):
        """
        Verify that the string representation of the bulk operation task includes the uploaded_by username.
        """
        bulk_operation = factories.BulkOperationTaskFactory()
        string_output = str(bulk_operation)
        self.assertIn(bulk_operation.uploaded_by.username, string_output)

    def test_save_assigns_uploaded_by(self):
        """
        Verify that the uploaded_by is assigned when saving the bulk operation task.
        """
        user = factories.UserFactory()
        bulk_operation = factories.BulkOperationTaskFactory.build(uploaded_by=None)
        bulk_operation.save(user=user)
        self.assertEqual(bulk_operation.uploaded_by, user)

    def test_bulk_operation_task_save_raises_error_without_user_or_uploaded_by(self):
        """
        Verify that an error is raised if the user or uploaded_by is not provided when saving.
        """
        with pytest.raises(ValueError, match="User is required to save the BulkOperationTask"):
            factories.BulkOperationTaskFactory(uploaded_by=None)
