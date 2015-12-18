import logging

from django.conf import settings
from elasticsearch import Elasticsearch

from course_discovery.apps.courses.config import COURSES_INDEX_CONFIG

logger = logging.getLogger(__name__)


class ElasticsearchTestMixin(object):
    @classmethod
    def setUpClass(cls):
        super(ElasticsearchTestMixin, cls).setUpClass()
        host = settings.ELASTICSEARCH['host']
        cls.index = settings.ELASTICSEARCH['index']
        cls.es = Elasticsearch(host)

    def setUp(self):
        super(ElasticsearchTestMixin, self).setUp()
        self.reset_index()
        self.refresh_index()

    def reset_index(self):
        """ Deletes and re-creates the Elasticsearch index. """

        index = self.index

        logger.info('Deleting index [%s]...', index)
        self.es.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        logger.info('...index deleted.')

        logger.info('Recreating index [%s]...', index)
        self.es.indices.create(index=index, body=COURSES_INDEX_CONFIG)
        logger.info('...done!')

    def refresh_index(self):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        # pylint: disable=unexpected-keyword-arg
        self.es.indices.refresh(index=self.index)
        self.es.cluster.health(index=self.index, wait_for_status='yellow', request_timeout=1)
