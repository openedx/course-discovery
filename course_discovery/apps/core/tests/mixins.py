import logging

from django.conf import settings
from haystack import connections as haystack_connections

from course_discovery.apps.core.utils import ElasticsearchUtils
from course_discovery.apps.course_metadata.models import Course, CourseRun

logger = logging.getLogger(__name__)


class ElasticsearchTestMixin(object):
    @classmethod
    def setUpClass(cls):
        super(ElasticsearchTestMixin, cls).setUpClass()
        cls.index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']
        # Make use of the changes in our custom ES backend
        # This is required for typeahead autocomplete to work in the tests
        connection = haystack_connections['default']
        cls.backend = connection.get_backend()
        # Without this line, haystack doesn't fully recreate the connection
        # The first test using this backend succeeds, but the following tests
        # do not set the Elasticsearch _mapping

    def setUp(self):
        super(ElasticsearchTestMixin, self).setUp()
        self.backend.setup_complete = False
        self.es = self.backend.conn
        self.reset_index()
        self.refresh_index()

    def reset_index(self):
        """ Deletes and re-creates the Elasticsearch index. """
        self.delete_index(self.index)
        ElasticsearchUtils.create_alias_and_index(self.es, self.index)

    def delete_index(self, index):
        """
        Deletes an index.

        Args:
            index (str): Name of index to delete

        Returns:
            None
        """
        logger.info('Deleting index [%s]...', index)
        self.es.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        logger.info('...index deleted.')

    def refresh_index(self):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        # pylint: disable=unexpected-keyword-arg
        self.es.indices.refresh(index=self.index)
        self.es.cluster.health(index=self.index, wait_for_status='yellow', request_timeout=1)

    def reindex_course_runs(self, course):
        index = haystack_connections['default'].get_unified_index().get_index(CourseRun)
        for course_run in course.course_runs.all():
            index.update_object(course_run)

    def reindex_courses(self, program):
        index = haystack_connections['default'].get_unified_index().get_index(Course)
        for course in program.courses.all():
            index.update_object(course)
            self.reindex_course_runs(course)
