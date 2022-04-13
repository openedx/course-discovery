from unittest import TestCase

import pytest

from course_discovery.apps.api.fields import ImageField
from course_discovery.apps.taxonomy_support.api.v1.serializers import CourseRecommendationsSerializer
from course_discovery.apps.taxonomy_support.api.v1.tests.factories import CourseRecommendationFactory


@pytest.mark.django_db
class TestsCourseRecommendationsSerializer(TestCase):
    """Test CourseRecommendationsSerializer"""
    serializer_class = CourseRecommendationsSerializer

    @classmethod
    def get_expected_data(cls, recommendation):
        """
        Generate expected data from CourseRecommendation object.
        """
        return {
            'id': recommendation.id,
            'key': recommendation.recommended_course.key,
            'title': recommendation.recommended_course.title,
            'owners': [
                {
                    'uuid': owner.uuid,
                    'key': owner.key,
                    'name': owner.name,
                    'auto_generate_course_run_keys': owner.auto_generate_course_run_keys,
                    'certificate_logo_image_url': owner.certificate_logo_image_url,
                    'logo_image_url': owner.logo_image.url
                } for owner in recommendation.recommended_course.authoring_organizations.all()
            ],
            'card_image_url': ImageField().to_representation(recommendation.recommended_course.image_url),
            'skills_intersection_ratio': float(recommendation.skills_intersection_ratio),
            'skills_intersection_length': float(recommendation.skills_intersection_length),
            'subjects_intersection_ratio': float(recommendation.subjects_intersection_ratio),
            'subjects_intersection_length': float(recommendation.subjects_intersection_length),
        }

    def test_data(self):
        """
        Tests serializer Data.
        """
        self.maxDiff = None
        recommendation = CourseRecommendationFactory()
        serializer = self.serializer_class(recommendation)
        expected = self.get_expected_data(recommendation)
        self.assertDictEqual(serializer.data, expected)
