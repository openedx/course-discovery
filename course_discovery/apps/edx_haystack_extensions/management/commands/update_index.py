import logging

from django.conf import settings
from django.core.management import CommandError
from haystack import connections as haystack_connections
from haystack.management.commands.update_index import Command as HaystackCommand

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


class Command(HaystackCommand):
    backends = []

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--disable-change-limit', action='store_true', dest='disable_change_limit',
            help='Disables checks limiting the number of records modified.'
        )

    def get_record_count(self, conn, index_name):
        return conn.count(index_name).get('count')

    def handle(self, *items, **options):
        self.backends = options.get('using')
        if not self.backends:
            self.backends = list(haystack_connections.connections_info.keys())

        alias_mappings = []

        # Use a timestamped index instead of the default in settings.
        for backend_name in self.backends:
            connection = haystack_connections[backend_name]
            backend = connection.get_backend()
            record_count = self.get_record_count(backend.conn, backend.index_name)
            alias, index_name = self.prepare_backend_index(backend)
            alias_mappings.append((backend, index_name, alias))

        super(Command, self).handle(*items, **options)

        # Set the alias (from settings) to the timestamped catalog.
        for backend, index, alias in alias_mappings:
            # Run a sanity check to ensure we aren't drastically changing the
            # index, which could be indicative of a bug.
            if not options.get('disable_change_limit', False):
                record_count_is_sane, index_info_string = self.sanity_check_new_index(backend.conn, index, record_count)
                if not record_count_is_sane:
                    raise CommandError('Sanity check failed for new index. ' + index_info_string)

            self.set_alias(backend, alias, index)

    def percentage_change(self, current, previous):
        try:
            return abs(current - previous) / previous
        except ZeroDivisionError:
            # pick large percentage for division by 0
            # This is done to fail the sanity check
            return 1

    def sanity_check_new_index(self, conn, index, previous_record_count):
        """ Ensure that we do not point to an index that looks like it has missing data. """
        current_record_count = conn.count(index).get('count')
        percentage_change = self.percentage_change(current_record_count, previous_record_count)

        # Verify there was not a big shift in record count
        record_count_is_sane = percentage_change < settings.INDEX_SIZE_CHANGE_THRESHOLD
        index_info_string = (
            'The previous index contained [{}] records. '
            'The new index contains [{}] records, a [{:.2f}%] change.'.format(
                previous_record_count, current_record_count, percentage_change * 100
            )
        )
        return record_count_is_sane, index_info_string

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
