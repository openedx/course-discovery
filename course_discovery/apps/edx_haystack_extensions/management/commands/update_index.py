import logging

from haystack import connections as haystack_connections
from haystack.management.commands.update_index import Command as HaystackCommand

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


class Command(HaystackCommand):
    backends = []

    def handle(self, *items, **options):
        self.backends = options.get('using')
        if not self.backends:
            self.backends = list(haystack_connections.connections_info.keys())

        alias_mappings = []

        # Use a timestamped index instead of the default in settings.
        for backend_name in self.backends:
            connection = haystack_connections[backend_name]
            backend = connection.get_backend()
            alias, index_name = self.prepare_backend_index(backend)
            alias_mappings.append((backend, index_name, alias))

        super(Command, self).handle(*items, **options)

        # Set the alias (from settings) to the timestamped catalog.
        # Temporarily commenting this out to test if update index command is still broken
        # for backend, index, alias in alias_mappings:
        #    self.set_alias(backend, alias, index)

    def set_alias(self, backend, alias, index):
        """
        Points the alias to the specified index.

        All other references made by the alias will be removed, however the referenced indexes will
        not be modified in any other manner.

        Args:
            backend (ElasticsearchSearchBackend): Elasticsearch backend with an open connection.
            alias (str): Name of the alias to set.
            index (str): Name of the index where the alias should point.

        Returns:
            None
        """
        body = {
            'actions': [
                {'remove': {'alias': alias, 'index': '*'}},
                {'add': {'alias': alias, 'index': index}},
            ]
        }
        backend.conn.indices.update_aliases(body)

    def prepare_backend_index(self, backend):
        """
        Prepares an index that will be used to store data by the backend.

        Args:
            backend (ElasticsearchSearchBackend): Backend to update.

        Returns:
            (tuple): tuple containing:

                alias(str): Recommended alias for the new index.
                index_name(str): Name of the newly-created index.
        """
        alias = backend.index_name
        index_name = ElasticsearchUtils.create_index(backend.conn, alias)
        backend.index_name = index_name
        return alias, index_name
