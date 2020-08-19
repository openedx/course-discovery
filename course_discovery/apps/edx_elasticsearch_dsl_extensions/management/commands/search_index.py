import contextlib
import datetime
import logging
import time
from collections import namedtuple
from copy import copy

from django.conf import settings
from django.core.management import CommandError
from django_elasticsearch_dsl.management.commands.search_index import Command as DjangoESDSLCommand
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl.connections import get_connection

from course_discovery.apps.core.utils import ElasticsearchUtils

OLD_AND_NEW_INDEX_NAMES = slice(2, 4)

AliasMapper = namedtuple('AliasMapper',
                         'document registered_index registered_index_name new_index_name alias record_count')
logger = logging.getLogger(__name__)


class Command(DjangoESDSLCommand):
    backends = []

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--update',
            action='store_const',
            dest='action',
            const='update',
            help='Update indices with sanity check. '
                 'Will be created a new index and populate with data. '
                 'The index will be masked with previous one to prevent missing data.'
        )
        parser.add_argument(
            '--disable-change-limit', action='store_true', dest='disable_change_limit',
            help='Disables checks limiting the number of records modified.'
        )
        parser.add_argument(
            '-u',
            '--using',
            action='append',
            default=[],
            help='Update only the named backend (can be used multiple times). '
                 'By default all backends will be updated.',
        )

    def handle(self, *args, **options):
        # pylint:disable=import-outside-toplevel
        from django.utils import translation
        translation.activate(settings.LANGUAGE_CODE)
        specified_backend = options.get('using')
        supported_backends = tuple(settings.ELASTICSEARCH_DSL.keys())
        if specified_backend and specified_backend not in supported_backends:
            msg = 'Specified backend [{0}] is not supported. Supported backends: {1}'.format(
                specified_backend, supported_backends
            )
            raise CommandError(msg)

        self.backends = (specified_backend,) if specified_backend else supported_backends
        action = options['action']
        models = self._get_models(options['models'])
        if action == 'update':
            self._update(models, options)
        else:
            super(Command, self).handle(**options)

    @staticmethod
    def get_record_count(document):
        return document.search().query().count()

    @contextlib.contextmanager
    def preserve_state_registered_indexes(self, state_to_update, models):
        # pylint:disable=protected-access
        for index, (__, new_name) in zip(registry.get_indices(models), state_to_update):
            index._name = new_name
        yield
        for index, (existed_name, __) in zip(registry.get_indices(models), state_to_update):
            index._name = existed_name

    def _create(self, models, options):
        for backend in self.backends:
            for index in registry.get_indices(models):
                created_index_info = ElasticsearchUtils.create_index(index, backend)
                es_connection = get_connection(backend)
                self.stdout.write(
                    'Creating index "{1}".\nSet alias "{0}" for index "{1}".'.format(
                        created_index_info.alias, created_index_info.name
                    )
                )
                self.set_alias(es_connection, created_index_info.alias, created_index_info.name)

    def _update(self, models, options):
        alias_mappings = []
        for index, document in zip(registry.get_indices(models), registry.get_documents(models)):
            record_count = self.get_record_count(document)
            alias, new_index_name = self.prepare_backend_index(index)
            # pylint:disable=protected-access
            alias_mappings.append(AliasMapper(document, index, index._name, new_index_name, alias, record_count))
        # Set the alias (from settings) to the timestamped catalog.
        run_attempts = 0
        indexes_pending = {key: '' for key in [x.new_index_name for x in alias_mappings]}
        conn = get_connection()
        while indexes_pending and run_attempts < 2:
            run_attempts += 1
            existed_and_new_index_names = [mapper[OLD_AND_NEW_INDEX_NAMES] for mapper in alias_mappings]
            with self.preserve_state_registered_indexes(existed_and_new_index_names, models):
                self._populate(models, options)
            for doc, registered_index, __, new_index_name, alias, record_count in alias_mappings:
                # Run a sanity check to ensure we aren't drastically changing the
                # index, which could be indicative of a bug.
                if new_index_name in indexes_pending and not options.get('disable_change_limit', False):
                    with self.preserve_state_registered_indexes(existed_and_new_index_names, models):
                        record_count_is_sane, index_info_string = self.sanity_check_new_index(
                            doc, new_index_name, record_count
                        )
                    if record_count_is_sane:
                        # pylint:disable=protected-access
                        registered_index._name = new_index_name
                        self.set_alias(conn, alias, new_index_name)
                        indexes_pending.pop(new_index_name, None)
                    else:
                        indexes_pending[new_index_name] = index_info_string
                else:
                    self.set_alias(conn, alias, new_index_name)
                    indexes_pending.pop(new_index_name, None)
        if indexes_pending:
            raise CommandError('Sanity check failed for new index(es): {}'.format(indexes_pending))

        return True

    @staticmethod
    def percentage_change(current, previous):
        if current == previous:
            return 0.0
        try:
            return abs(current - previous) / previous
        except ZeroDivisionError:
            # pick large percentage for division by 0
            # This is done to fail the sanity check
            return 1

    def sanity_check_new_index(self, document, new_index_name, previous_record_count):
        """ Ensure that we do not point to an index that looks like it has missing data. """
        current_record_count = document.search().query().count()
        percentage_change = self.percentage_change(current_record_count, previous_record_count)
        # Verify there was not a big shift in record count
        record_count_is_sane = percentage_change < settings.INDEX_SIZE_CHANGE_THRESHOLD
        conn = get_connection()
        if not record_count_is_sane:
            attempts = 0
            while attempts < 2:
                attempts += 1
                current_attempt_record_count = self.get_record_count(document)
                current_attempt_percentage_change = self.percentage_change(
                    current_attempt_record_count, previous_record_count)
                alternate_current_record_count = conn.search({"query": {"match_all": {}}}, index=new_index_name).get(
                    'hits', {}).get('total', {}).get('value', 0)
                message = '''
    Sanity check failed for attempt #{0}.
    Index name: {1}
    Percentage change: {2}
    Base record count: {3}
    Search record count: {4}
                '''.format(
                    attempts,
                    new_index_name,
                    str(int(round(current_attempt_percentage_change * 100, 0))) + '%',
                    current_attempt_record_count,
                    alternate_current_record_count
                )
                logger.info(message)
                logger.info('...sleeping for 5 seconds...')
                time.sleep(5)

        index_info_string = (
            'The previous index contained [{}] records. '
            'The new index contains [{}] records, a [{:.2f}%] change.'.format(
                previous_record_count, current_record_count, percentage_change * 100
            )
        )

        return record_count_is_sane, index_info_string

    def prepare_backend_index(self, registered_index, backend='default'):
        """
        Prepares an index that will be used to store data by the backend.

        Args:
            backend (ElasticsearchSearchBackend): Backend to update.

        Returns:
            (tuple): tuple containing:

                alias(str): Recommended alias for the new index.
                index_name(str): Name of the newly-created index.
        """
        copied_registered_index = copy(registered_index)
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        # pylint:disable=protected-access
        existed_index_name = copied_registered_index._name
        alias, *_ = copied_registered_index.get_alias(using=backend).get(existed_index_name, {}).get('aliases').keys()
        new_index_name = '{alias}_{timestamp}'.format(alias=alias, timestamp=timestamp)
        copied_registered_index._name = new_index_name
        self.stdout.write("Creating index '{}'".format(copied_registered_index._name))
        copied_registered_index.create(using=backend)

        return alias, new_index_name

    def set_alias(self, connection, alias, index):
        """
        Points the alias to the specified index.

        All other references made by the alias will be removed, however the referenced indexes will
        not be modified in any other manner.

        Args:
            connection (ElasticsearchSearchBackend): Elasticsearch backend with an open connection.
            alias (str): Name of the alias to set.
            index (str): Name of the index where the alias should point.

        Returns:
            None
        """
        body = {
            'actions': [
                {"remove": {"alias": alias, "index": '{0}_*'.format(alias)}},
                {"add": {"alias": alias, "index": index}}
            ]
        }

        connection.indices.update_aliases(body)
