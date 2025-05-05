from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import BulkOperationStatus, BulkOperationType
from course_discovery.apps.course_metadata.models import BulkOperationTask


class BulkOperationTaskTests(OAuth2Mixin, APITestCase):
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

        self.create_url = reverse('api:v1:bulkoperationtask-list')

    def test_create_bulk_task_assigns_uploaded_by(self):
        """
        Test that the BulkOperationTask is created with the correct uploaded_by user.
        The uploaded_by field should be set to the user who created the task.
        """
        response = self.client.post(self.create_url, {
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
        task = BulkOperationTask.objects.create(
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

    def test_authentication_required(self):
        """
        Test that authentication is required to access the create endpoint
        """
        self.client.logout()
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_upload_validates_csv(self):
        """
        Test that the uploaded file is validated as a CSV file.
        """
        invalid_file = SimpleUploadedFile("test.txt", b"not,a,csv", content_type="text/plain")
        response = self.client.post(self.create_url, {
            'csv_file': invalid_file,
            'task_type': BulkOperationType.CourseCreate,
            'status': BulkOperationStatus.Pending,
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('csv_file', response.data)
