import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from haystack import connections as haystack_connections

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    backends = []
    help = 'This command will purge the oldest indexes, freeing up disk space.  This command will never delete the ' \
           'currently used index.'

    def handle(self, *_args, **options):
        self.backends = options.get('using')
        if not self.backends:
            self.backends = list(haystack_connections.connections_info.keys())

        for backend_name in self.backends:
            connection = haystack_connections[backend_name]
            backend = connection.get_backend()
            indices_client = backend.conn.indices
            current_alias_name = backend.index_name
            self.remove_unused_indexes(indices_client=indices_client, current_alias_name=current_alias_name)

    def remove_unused_indexes(self, indices_client, current_alias_name):
        """
        Removes all but the newest (Elasticsearch) indexes, using the configured value to limit deletions

        Args:
            indices_client (IndicesClient): Elasticsearch Index API client, used to list/delete index
            current_alias_name (str): The name of the configured alias, used for lookup

        Returns:
            None
        """
        sorted_indexes_by_timestamp = self.get_indexes_sorted_by_timestamp(indices_client=indices_client,
                                                                           index_prefix=current_alias_name)
        index_count = len(sorted_indexes_by_timestamp)
        logger.info(f'Found {index_count} indexes')

        # Remove current index from list so we don't delete it
        current_alias = indices_client.get_alias(name=current_alias_name)
        sorted_indexes_by_timestamp = list(set(sorted_indexes_by_timestamp) - set(current_alias.keys()))

        num_indices_to_remove = len(sorted_indexes_by_timestamp) - settings.HAYSTACK_INDEX_RETENTION_LIMIT

        if num_indices_to_remove > 0:
            indices_to_remove = sorted_indexes_by_timestamp[:num_indices_to_remove]
            logger.info('Deleting indices %s...', indices_to_remove)
            indices_client.delete(index=','.join(indices_to_remove))
            logger.info('Successfully deleted indices %s.', indices_to_remove)
        else:
            logger.info('No indices to remove.')

    def get_indexes_sorted_by_timestamp(self, indices_client, index_prefix):
        """
        Uses the haystack connection to fetch the (Elasticsearch) indexes, sorted by timestamp

        Args:
            indices_client (IndicesClient): Elasticsearch Index API client, used to fetch index info
            index_prefix (str): The string prefix for the index, used to match the indexes fetched

        Returns:
            sorted_indexes_by_timestamp (list): The sorted listing of index names
        """
        # Elasticsearch in AWS is not a full implementation of ES, and we need to use the (more verbose) status
        # endpoint instead of the (more succinct) settings endpoint. For more information, see
        # http://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/aes-supported-es-operations.html
        all_index_status = indices_client.status()
        all_indexes = list(all_index_status['indices'].keys())
        all_current_indexes = [index_name for index_name in all_indexes if index_name.startswith(index_prefix + '_')]
        return sorted(all_current_indexes)
