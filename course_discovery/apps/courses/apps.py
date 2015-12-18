import logging

from django.apps import AppConfig
from django.conf import settings
from elasticsearch import Elasticsearch, TransportError

from course_discovery.apps.courses.config import COURSES_INDEX_CONFIG

logger = logging.getLogger(__name__)


class CoursesConfig(AppConfig):
    name = 'courses'
    verbose_name = 'Courses'

    def ready(self):
        if settings.ELASTICSEARCH.get('connect_on_startup', False):
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
