import logging

from django.conf import settings
from django.core.management import BaseCommand

from elasticsearch import Elasticsearch, TransportError

from course_discovery.apps.courses.config import COURSES_INDEX_CONFIG

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Install any required elasticsearch indexes'

    def handle(self, *args, **options):
        host = settings.ELASTICSEARCH['host']
        index = settings.ELASTICSEARCH['index']

        logger.info('Attempting to establish initial connection to Elasticsearch host [%s]...', host)
        es = Elasticsearch(host, sniff_on_start=True)
        logger.info('...success!')

        logger.info('Making sure index [%s] exists...', index)
        try:
            es.indices.create(index=index, body=COURSES_INDEX_CONFIG)
            logger.info('...index created.')
        except TransportError as e:
            if e.status_code == 400:
                logger.info('...index already exists.')
            else:
                raise
