import logging

import pytest
from django.conf import settings
from haystack import connections as haystack_connections

from course_discovery.apps.core.utils import ElasticsearchUtils
from course_discovery.apps.course_metadata.models import Course, CourseRun

logger = logging.getLogger(__name__)


@pytest.mark.usefixtures('haystack_default_connection')
class ElasticsearchTestMixin(object):
    def setUp(self):
        super(ElasticsearchTestMixin, self).setUp()
        self.index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']
        connection = haystack_connections['default']
        self.es = connection.get_backend().conn

    def refresh_index(self):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        ElasticsearchUtils.refresh_index(self.es, self.index)

    def reindex_course_runs(self, course):
        index = haystack_connections['default'].get_unified_index().get_index(CourseRun)
        for course_run in course.course_runs.all():
            index.update_object(course_run)

    def reindex_courses(self, program):
        index = haystack_connections['default'].get_unified_index().get_index(Course)
        for course in program.courses.all():
            index.update_object(course)
            self.reindex_course_runs(course)
