import logging

from django.conf import settings
from elasticsearch import Elasticsearch

from au_amber.apps.courses.utils import ElasticsearchUtils

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
