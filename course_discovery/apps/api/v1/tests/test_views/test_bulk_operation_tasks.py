from ddt import data, ddt, unpack
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.timezone import now
from django_celery_results.models import TaskResult
from rest_framework import status

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import BulkOperationStatus, BulkOperationType
from course_discovery.apps.course_metadata.models import BulkOperationTask
from course_discovery.apps.course_metadata.tests.factories import BulkOperationTaskFactory


@ddt
class BulkOperationTaskViewSetTests(OAuth2Mixin, APITestCase):
    """
    Test Suite for BulkOperationTaskViewSet.
    """
    CREATE_BULK_OPERATION_TASK_URL = reverse('api:v1:bulkoperationtask-list')

    def setUp(self):
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.csv_file = SimpleUploadedFile(
            "test.csv", b"name,description\nCourse 1,Description 1\nCourse 2,Description 2",
            content_type="text/csv"
        )

    def test_create_bulk_task_assigns_uploaded_by(self):
        """
        Test that the BulkOperationTask is created with the correct uploaded_by user.
        The uploaded_by field should be set to the user who created the task.
        """
        response = self.client.post(self.CREATE_BULK_OPERATION_TASK_URL, {
            'csv_file': self.csv_file,
            'task_type': BulkOperationType.CourseCreate,
            'status': BulkOperationStatus.Pending,
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = BulkOperationTask.objects.get(id=response.data['id'])
        self.assertEqual(task.uploaded_by, self.user)
        self.assertEqual(response.data['uploaded_by'], self.user.username)

    def test_uploaded_by_is_username_in_response(self):
        """
        Test that the uploaded_by field in the response is the username of the user who created the task.
        """
        task = BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Pending,
        )
        url = reverse('api:v1:bulkoperationtask-detail', args=[task.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uploaded_by'], self.user.username)
        self.assertTrue(response.data['csv_file'].endswith('.csv'))

    def test_no_auth(self):
        """
        Test that authentication is required to access the create endpoint
        """
        self.client.logout()
        response = self.client.get(self.CREATE_BULK_OPERATION_TASK_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_file(self):
        """
        Test that BulkOperationTaskViewSet rejects invalid file types and returns a bad request error.
        """
        invalid_file = SimpleUploadedFile("test.txt", b"not,a,csv", content_type="text/plain")
        response = self.client.post(self.CREATE_BULK_OPERATION_TASK_URL, {
            'csv_file': invalid_file,
            'task_type': BulkOperationType.CourseCreate,
            'status': BulkOperationStatus.Pending,
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('csv_file', response.data)

    def test_bulk_operation_task_order_by_status(self):
        """
        Test that the BulkOperationTask can be ordered by status field.
        """
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Completed,
        )
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Pending,
        )

        url = f"{self.CREATE_BULK_OPERATION_TASK_URL}?ordering=status"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['results'][0]['status'], BulkOperationStatus.Completed)
        self.assertEqual(response.data['results'][1]['status'], BulkOperationStatus.Pending)

    def test_bulk_operation_task_order_by_created_field(self):
        """
        Test that the BulkOperationTask can be ordered by created field.
        """
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Pending,
        )
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Completed,
        )

        url = f"{self.CREATE_BULK_OPERATION_TASK_URL}?ordering=-created"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['results'][0]['created'], response.data['results'][1]['created'])

        url = f"{self.CREATE_BULK_OPERATION_TASK_URL}?ordering=created"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(response.data['results'][0]['created'], response.data['results'][1]['created'])

    def test_bulk_operation_task_filter_by_status(self):
        """
        Test that the BulkOperationTask can be filtered by status field.
        """
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Pending,
        )
        BulkOperationTaskFactory(
            csv_file=self.csv_file,
            uploaded_by=self.user,
            task_type=BulkOperationType.CourseCreate,
            status=BulkOperationStatus.Completed,
        )

        url = f"{self.CREATE_BULK_OPERATION_TASK_URL}?status={BulkOperationStatus.Pending}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], BulkOperationStatus.Pending)

    def test_bulk_operation_task_viewset_permissions(self):
        """
        Test isStaffOrSuperuser permission is required to access the BulkOperationTaskViewSet.
        """
        non_staff_user = UserFactory(is_staff=False, is_superuser=False)
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        response = self.client.post(self.CREATE_BULK_OPERATION_TASK_URL, {
            'csv_file': self.csv_file,
            'task_type': BulkOperationType.CourseCreate,
            'status': BulkOperationStatus.Pending,
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @data(('task_type',), ('csv_file',))
    @unpack
    def test_missing_required_fields(self, missing_field):
        """
        Test that the BulkOperationTaskViewSet returns a 400 error when required fields are missing.
        """
        request_data = {
            'csv_file': self.csv_file,
            'task_type': BulkOperationType.CourseCreate,
        }
        request_data.pop(missing_field)
        with self.subTest(missing_field=missing_field):
            response = self.client.post(self.CREATE_BULK_OPERATION_TASK_URL, request_data, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(missing_field, response.data)

    def test_detail_view_includes_result_attr__query_param_present(self):
        """
        Test that the result field is populated if include_result=true is passed.
        """
        task = BulkOperationTaskFactory(uploaded_by=self.user, task_id='dummy-task-id')
        TaskResult.objects.create(task_id='dummy-task-id', result='{"message": "done"}', date_done=now())

        url = reverse('api:v1:bulkoperationtask-detail', args=[task.id]) + '?include_result=true'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], '{"message": "done"}')

    def test_detail_view_includes_result_param__no_task_result_found(self):
        """
        Test that the result field is None if include_result=true is passed but no TaskResult exists.
        """
        task = BulkOperationTaskFactory(uploaded_by=self.user, task_id='non-existent-id')

        url = reverse('api:v1:bulkoperationtask-detail', args=[task.id]) + '?include_result=true'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('result', response.data)
        self.assertIsNone(response.data['result'])
