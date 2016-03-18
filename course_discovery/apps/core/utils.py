import datetime
import logging

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
            es.indices.create(index=index)
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
