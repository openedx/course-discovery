import logging

from django.conf import settings
from elasticsearch import Elasticsearch

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


class ElasticsearchTestMixin(object):
    es = None
    index = None

    @classmethod
    def setUpClass(cls):
        super(ElasticsearchTestMixin, cls).setUpClass()
        host = settings.HAYSTACK_CONNECTIONS['default']['URL']
        cls.index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']
        cls.es = Elasticsearch(host)

    @classmethod
    def tearDownClass(cls):
        cls.delete_index(cls.index)

    @classmethod
    def reset_index(cls):
        """ Deletes and re-creates the Elasticsearch index. """
        cls.delete_index(cls.index)
        ElasticsearchUtils.create_alias_and_index(cls.es, cls.index)

    @classmethod
    def delete_index(cls, index):
        """
        Deletes an index.

        Args:
            index (str): Name of index to delete

        Returns:
            None
        """
        logger.info('Deleting index [%s]...', index)
        cls.es.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        logger.info('...index deleted.')

    @classmethod
    def refresh_index(cls):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        # pylint: disable=unexpected-keyword-arg
        cls.es.indices.refresh(index=cls.index)
        cls.es.cluster.health(index=cls.index, wait_for_status='yellow', request_timeout=1)

    def setUp(self):
        super(ElasticsearchTestMixin, self).setUp()
        self.reset_index()
        self.refresh_index()
