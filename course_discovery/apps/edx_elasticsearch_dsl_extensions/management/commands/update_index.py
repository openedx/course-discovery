import datetime
import logging
import time
from collections import namedtuple

from django.conf import settings
from django.core.management import CommandError
from django_elasticsearch_dsl.management.commands.search_index import Command as DjangoESDSLCommand
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import Mapping
from elasticsearch_dsl.connections import get_connection

from course_discovery.apps.core.utils import ElasticsearchUtils

OLD_AND_NEW_INDEX_NAMES = slice(2, 4)

AliasMapper = namedtuple('AliasMapper',
                         'document registered_index new_index_name alias record_count')
logger = logging.getLogger(__name__)


class Command(DjangoESDSLCommand):
    help = 'Manage elasticsearch index.'
    backends = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--models',
            metavar='app[.model]',
            type=str,
            nargs='*',
            help="Specify the model or app to be updated in elasticsearch"
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            dest='parallel',
            help='Run populate/rebuild update multi threaded'
        )
        parser.add_argument(
            '--no-parallel',
            action='store_false',
            dest='parallel',
            help='Run populate/rebuild update single threaded'
        )
        parser.set_defaults(parallel=getattr(settings, 'ELASTICSEARCH_DSL_PARALLEL', False))
        parser.add_argument(
            '--refresh',
            action='store_true',
            dest='refresh',
            default=None,
            help='Refresh indices after populate/rebuild'
        )
        parser.add_argument(
            '--no-count',
            action='store_false',
            default=True,
            dest='count',
            help='Do not include a total count in the summary log line'
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
        from django.utils import translation  # pylint: disable=import-outside-toplevel
        translation.activate(settings.LANGUAGE_CODE)
        specified_backend = options.get('using')
        supported_backends = tuple(settings.ELASTICSEARCH_DSL.keys())
        if specified_backend and specified_backend not in supported_backends:
            msg = 'Specified backend [{0}] is not supported. Supported backends: {1}'.format(
                specified_backend, supported_backends
            )
            raise CommandError(msg)

        self.backends = (specified_backend,) if specified_backend else supported_backends
        models = self._get_models(options['models'])
        self._update(models, options)

    def _update(self, models, options):
        """
        Update indices with sanity check.

        Will be created a new index and populate with data.
        The index will be masked with previous one to prevent missing data.
        """

        alias_mappings = []
        for document in registry.get_documents(models):
            # pylint: disable=protected-access
            index = document._index
            record_count = self.get_record_count(document)
            alias, new_index_name = self.prepare_backend_index(index)
            alias_mappings.append(AliasMapper(document, index, new_index_name, alias, record_count))
        # Set the alias (from settings) to the timestamped catalog.
        run_attempts = 0
        indexes_pending = {key: '' for key in [x.new_index_name for x in alias_mappings]}
        conn = get_connection()
        while indexes_pending and run_attempts < 1:  # Only try once, as retries gave buggy results. See VAN-391
            run_attempts += 1
            self._populate(models, options)
            for doc, __, new_index_name, alias, record_count in alias_mappings:
                # Run a sanity check to ensure we aren't drastically changing the
                # index, which could be indicative of a bug.
                if new_index_name in indexes_pending and not options.get('disable_change_limit', False):
                    record_count_is_sane, index_info_string = self.sanity_check_new_index(
                        run_attempts, doc, new_index_name, record_count
                    )
                    if record_count_is_sane:
                        ElasticsearchUtils.set_alias(conn, alias, new_index_name)
                        ElasticsearchUtils.update_max_result_window(conn, settings.MAX_RESULT_WINDOW, new_index_name)
                        indexes_pending.pop(new_index_name, None)
                    else:
                        indexes_pending[new_index_name] = index_info_string
                else:
                    ElasticsearchUtils.set_alias(conn, alias, new_index_name)
                    ElasticsearchUtils.update_max_result_window(conn, settings.MAX_RESULT_WINDOW, new_index_name)
                    indexes_pending.pop(new_index_name, None)

        for index_alias_mapper in alias_mappings:
            index_alias_mapper.registered_index._name = index_alias_mapper.alias  # pylint: disable=protected-access

        if indexes_pending:
            raise CommandError('Sanity check failed for the new index(es): {}'.format(indexes_pending))

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

    def sanity_check_new_index(self, attempt, document, new_index_name, previous_record_count):
        """ Ensure that we do not point to an index that looks like it has missing data. """
        current_record_count = self.get_record_count(document)
        percentage_change = self.percentage_change(current_record_count, previous_record_count)

        # Verify there was not a big shift in record count
        record_count_is_sane = percentage_change < settings.INDEX_SIZE_CHANGE_THRESHOLD

        # Spot check a known-flaky field type to detect VAN-391
        aggregation_type = Mapping.from_es(new_index_name)['aggregation_key'].name
        record_count_is_sane = record_count_is_sane and aggregation_type == 'keyword'

        if not record_count_is_sane:
            conn = get_connection()
            alternate_current_record_count = conn.search({"query": {"match_all": {}}}, index=new_index_name).get(
                'hits', {}).get('total', {}).get('value', 0)
            message = '''
        Sanity check failed for attempt #{0}.
        Index name: {1}
        Percentage change: {2}
        Previous record count: {3}
        Base record count: {4}
        Search record count: {5}
        Aggregation key type: {6}
                '''.format(
                attempt,
                new_index_name,
                str(int(round(percentage_change * 100, 0))) + '%',
                previous_record_count,
                current_record_count,
                alternate_current_record_count,
                aggregation_type,
            )
            logger.info(message)
            logger.info('...sleeping for 5 seconds...')
            time.sleep(5)
        else:
            message = '''
        Sanity check passed for attempt #{0}.
        Index name: {1}
        Percentage change: {2}
        Previous record count: {3}
        Current record count: {4}
                '''.format(
                attempt,
                new_index_name,
                str(int(round(percentage_change * 100, 0))) + '%',
                previous_record_count,
                current_record_count
            )
            logger.info(message)

        index_info_string = (
            'The previous index contained [{}] records. '
            'The new index contains [{}] records, a [{:.2f}%] change.'.format(
                previous_record_count, current_record_count, percentage_change * 100
            )
        )

        return record_count_is_sane, index_info_string

    @staticmethod
    def get_record_count(document):
        return document.search().query().count()

    def prepare_backend_index(self, registered_index, backend='default'):
        """
        Prepares an index that will be used to store data by the backend.

        Args:
            registered_index (Index): django elasticsearch index instance.
            backend (ElasticsearchSearchBackend): Backend to update.

        Returns:
            (tuple): tuple containing:

                alias(str): Recommended alias for the new index.
                index_name(str): Name of the newly-created index.
        """
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        # pylint: disable=protected-access
        computed_alias = ElasticsearchUtils.get_alias_by_index_name(registered_index._name)
        new_index_name = '{alias}_{timestamp}'.format(alias=computed_alias, timestamp=timestamp)
        registered_index._name = new_index_name
        self.stdout.write("Creating index '{}'".format(registered_index._name))
        registered_index.create(using=backend)

        return computed_alias, new_index_name
