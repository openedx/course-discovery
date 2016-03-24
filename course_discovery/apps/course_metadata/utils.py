import datetime
import logging

from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.config import COURSES_INDEX_CONFIG
from course_discovery.apps.course_metadata.models import Course, CourseRun, Seat

logger = logging.getLogger(__name__)


class ElasticsearchUtils(object):
    @classmethod
    def create_alias_and_index(cls, es, alias):
        logger.info('Making sure alias [%s] exists...', alias)

        if es.indices.exists_alias(name=alias):
            # If the alias exists, and points to an open index, we are all set.
            logger.info('...alias exists.')
        else:
            # Create an index with a unique (timestamped) name
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            index = '{alias}_{timestamp}'.format(alias=alias, timestamp=timestamp)
            es.indices.create(index=index, body=COURSES_INDEX_CONFIG)
            logger.info('...index [%s] created.', index)

            # Point the alias to the new index
            body = {
                'actions': [
                    {'remove': {'alias': alias, 'index': '*'}},
                    {'add': {'alias': alias, 'index': index}},
                ]
            }
            es.indices.update_aliases(body)
            logger.info('...alias updated.')


class CourseRunRefreshUtils(object):
    """ Course refresh utility. """
    @classmethod
    def refresh_all(cls, access_token):
        """
        Refresh course run data from the raw data sources for all courses.
        Args:
            access_token (str): Access token used to connect to data sources.
        Returns:
            None
        """
        pass
