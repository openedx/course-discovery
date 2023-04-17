"""
Tests for the django management command `refresh_course_reviews`.
"""
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase
from pytest import mark
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.models import CourseReview

LOGGER_NAME = 'course_discovery.apps.course_metadata.management.commands.refresh_course_reviews'


@mark.django_db
class RefreshCourseReviewsCommandTests(TestCase):
    """
    Test command `refresh_course_reviews`.
    """

    command = 'refresh_course_reviews'

    @mock.patch(
        'course_discovery.apps.course_metadata.management.'
        'commands.refresh_course_reviews.Command.get_query_results_from_snowflake'
    )
    def test_refresh_course_reviews(
            self,
            mock_get_query_results,
    ):
        """
        Test that refresh_course_reviews command works correctly and saves correct data in CourseReview model.
        """
        review_data = {
            'reviews_count': 5,
            'avg_course_rating': 4.400000,
            'confident_learners_percentage': 80.000000,
            'most_common_goal': 'Learn valuable skills',
            'most_common_goal_learners_percentage': 80.000000,
            'total_enrollments': 705,
        }
        course_review_1 = [
            'ACCA+ML001',
            review_data['reviews_count'],
            review_data['avg_course_rating'],
            review_data['confident_learners_percentage'],
            review_data['most_common_goal'],
            review_data['most_common_goal_learners_percentage'],
            review_data['total_enrollments']
        ]

        course_review_2 = [
            'CatalystX+EMOTX1x',
            review_data['reviews_count'],
            review_data['avg_course_rating'],
            review_data['confident_learners_percentage'],
            review_data['most_common_goal'],
            review_data['most_common_goal_learners_percentage'],
            review_data['total_enrollments']
        ]
        mock_get_query_results.return_value = [course_review_1, course_review_2]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    '[Refresh Course Reviews]  Process started with option dry_run=True.'
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'[Refresh Course Reviews] Creating/updating record with following data for {course_review_1[0]}:'
                    f' {review_data}'
                ),
                (
                    LOGGER_NAME,
                    'INFO',
                    f'[Refresh Course Reviews] Creating/updating record with following data for {course_review_2[0]}:'
                    f' {review_data}'
                ),
            )

            assert len(CourseReview.objects.all()) == 2

    @mock.patch(
        'course_discovery.apps.course_metadata.management.'
        'commands.refresh_course_reviews.Command.get_query_results_from_snowflake'
    )
    def test_refresh_course_reviews_failure(
            self,
            mock_get_query_results,
    ):
        """
        Test that refresh_course_reviews command logs correct message upon a failure.
        """
        review_data = {
            'reviews_count': 5,
            'avg_course_rating': 4.400000,
            'confident_learners_percentage': 80.000000,
            'most_common_goal': 'Learn valuable skills',
            'most_common_goal_learners_percentage': 80.000000,
            'total_enrollments': 705,
        }
        course_review = [
            'CatalystX+EMOTX1x',
            'invalid-reviews-count',
            review_data['avg_course_rating'],
            review_data['confident_learners_percentage'],
            review_data['most_common_goal'],
            review_data['most_common_goal_learners_percentage'],
            review_data['total_enrollments']
        ]
        mock_get_query_results.return_value = [course_review]
        error_msg = 'One or more course reviews were not successfully created or updated. Please check above logs' \
                    ' for more details.'
        with self.assertRaisesRegex(CommandError, error_msg):
            call_command(self.command)
        assert len(CourseReview.objects.all()) == 0
