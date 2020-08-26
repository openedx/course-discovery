import logging
from collections import namedtuple

from django.conf import settings
from django.core.management import CommandError
from django_elasticsearch_dsl.management.commands.search_index import Command as DjangoESDSLCommand
from django_elasticsearch_dsl.registries import registry
from elasticsearch.exceptions import NotFoundError
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
        super(Command, self).handle(**options)

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
                ElasticsearchUtils.set_alias(es_connection, created_index_info.alias, created_index_info.name)

    def _delete(self, models, options):
        # pylint: disable=protected-access
        index_names = [index._name for index in registry.get_indices(models)]
        if not options['force']:
            response = input(
                "Are you sure you want to delete "
                "the '{}' indexes? [y/N]: ".format(", ".join(index_names)))
            if response.lower() != 'y':
                self.stdout.write('Aborted')
                return False

        for index in registry.get_indices(models):
            try:
                index_alias = index.get_alias()
            except NotFoundError:
                continue
            index_name, *_ = index_alias.keys()
            index._name = index_name
            self.stdout.write("Deleting index '{}'".format(index._name))
            index.delete(ignore=404)
        return True
