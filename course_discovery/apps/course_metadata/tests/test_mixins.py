from unittest.mock import patch

from django.test import TestCase

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.search_indexes.documents import CourseDocument
from course_discovery.apps.course_metadata.tests import factories


class TestSearchAfterMixin(ElasticsearchTestMixin, TestCase):
    """
    Unit tests for SearchAfterMixin.
    Uses a proxy model `CourseProxy` that extends this mixin so we can replicate the behavior for Courses.
    """
    def setUp(self):
        super().setUp()

        self.total_courses = 5
        factories.CourseFactory.create_batch(self.total_courses)

    @patch("course_discovery.apps.course_metadata.models.registry.get_documents")
    def test_fetch_all_courses(self, mock_get_documents):
        query = 'Course*'
        mock_get_documents.return_value = [CourseDocument]

        queryset = factories.CourseProxy.search(query=query, page_size=2)

        unique_items = set(queryset)
        self.assertEqual(len(queryset), len(unique_items), 'Queryset contains duplicate entries.')
        self.assertEqual(len(queryset), self.total_courses)

    def test_wildcard_query_early_exit(self):
        """
        Test the early exit optimization when the query is `(*)`.
        """
        query = '*'

        queryset = factories.CourseProxy.search(query=query)

        self.assertEqual(len(queryset), self.total_courses)
        self.assertQuerySetEqual(
            queryset.order_by("id"),
            factories.Course.objects.all().order_by("id"),
            transform=lambda x: x
        )
