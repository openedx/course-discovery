from rest_framework import status
from rest_framework.reverse import reverse

from course_discovery.apps.api.serializers import CourseReviewSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import CourseReview


class CourseReviewViewSetTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True)
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def test_retrieve_course_review(self):
        course_review = CourseReview.objects.create(
            course_key='math101+11',
            reviews_count=100,
            avg_course_rating=4.5,
            confident_learners_percentage=0.85,
            most_common_goal=CourseReview.JOB_ADVANCEMENT,
            most_common_goal_learners_percentage=0.9,
            total_enrollments=500
        )

        url = reverse('api:v1:course-review-detail', kwargs={'course_key': course_review.course_key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = CourseReviewSerializer(course_review)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_nonexistent_course_review(self):
        course_key = 'nonexistent-course-key'
        url = reverse('api:v1:course-review-detail', kwargs={'course_key': course_key})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
