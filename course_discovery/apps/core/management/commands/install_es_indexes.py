import logging

from django.conf import settings
from django.core.management import BaseCommand
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl.connections import get_connection

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Install any required Elasticsearch indexes'

    def handle(self, *args, **options):
        for backend_name, host_cong in settings.ELASTICSEARCH_DSL.items():
            logger.info('Attempting to establish initial connection to Elasticsearch host [%s]...', host_cong['hosts'])
            es_connection = get_connection(backend_name)
            es_connection.ping()
            logger.info('...success!')

            for index in registry.get_indices():
                ElasticsearchUtils.create_alias_and_index(es_connection, index, backend_name)
