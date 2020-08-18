from django.conf import settings
from elasticsearch_dsl.connections import get_connection


class SearchIndexTestMixin:
    conn = None

    def setUp(self):
        super().setUp()
        self.conn = get_connection()

    def tearDown(self):
        """ Remove the indexes we created and reset the backend index_name."""
        for index_name in settings.ELASTICSEARCH_INDEX_NAMES.values():
            self.conn.indices.delete(index=index_name + '_*')
        super().tearDown()
