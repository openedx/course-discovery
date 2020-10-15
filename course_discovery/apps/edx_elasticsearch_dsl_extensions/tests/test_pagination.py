from django.conf import settings
from django.test import override_settings, TestCase
from elasticsearch_dsl.query import Q as ESDSLQ

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.search_indexes.documents import CourseDocument
from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import DEFAULT_SIZE


class TestSearchPagination(ElasticsearchTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.total_courses = 50
        for _ in range(self.total_courses):
            CourseFactory()

    @override_settings(ELASTICSEARCH_DSL_LOAD_PER_QUERY=100)
    def test_fetch_all_courses(self):
        search_results = CourseDocument.search().query(ESDSLQ('match_all')).execute()
        assert len(search_results) == self.total_courses

    @override_settings()
    def test_fetch_courses_when_no_dsl_load_per_query_settings(self):
        del settings.ELASTICSEARCH_DSL_LOAD_PER_QUERY
        search_results = CourseDocument.search().query(ESDSLQ('match_all')).execute()
        assert len(search_results) == DEFAULT_SIZE

    def test_fetch_courses_with_specific_size(self):
        desired_size = 25
        search_results = CourseDocument.search().query(ESDSLQ('match_all'))[:desired_size].execute()
        assert len(search_results) == desired_size
