import logging

from django.conf import settings
from django.core.management import BaseCommand
from elasticsearch import Elasticsearch

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Install any required Elasticsearch indexes'

    def handle(self, *args, **options):
        host = settings.HAYSTACK_CONNECTIONS['default']['URL']
        alias = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']

        logger.info('Attempting to establish initial connection to Elasticsearch host [%s]...', host)
        es = Elasticsearch(host)
        logger.info('...success!')

        ElasticsearchUtils.create_alias_and_index(es, alias)
