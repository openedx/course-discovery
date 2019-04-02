import datetime
import logging

from django.conf import settings

from course_discovery.settings.process_synonyms import get_synonyms

logger = logging.getLogger(__name__)


def serialize_datetime(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ') if d else None


class ElasticsearchUtils(object):
    @classmethod
    def create_alias_and_index(cls, es_connection, alias):
        logger.info('Making sure alias [%s] exists...', alias)

        if es_connection.indices.exists_alias(name=alias):
            # If the alias exists, and points to an open index, we are all set.
            logger.info('...alias exists.')
        else:
            index = cls.create_index(es_connection=es_connection, prefix=alias)
            # Point the alias to the new index
            body = {
                'actions': [
                    {'remove': {'alias': alias, 'index': '*'}},
                    {'add': {'alias': alias, 'index': index}},
                ]
            }
            es_connection.indices.update_aliases(body)
            logger.info('...alias updated.')

    @classmethod
    def create_index(cls, es_connection, prefix):
        """
        Creates a new index whose name is prefixed with the specified value.

        Args:
            es_connection (Elasticsearch): Elasticsearch connection - the connection object as created in the
             ElasticsearchSearchBackend class - the 'conn' attribute
            prefix (str): Alias for the connection, used as prefix for the index name

        Returns:
            index_name (str): Name of the new index.
        """
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        index_name = '{alias}_{timestamp}'.format(alias=prefix, timestamp=timestamp)
        index_settings = settings.ELASTICSEARCH_INDEX_SETTINGS
        index_settings['settings']['analysis']['filter']['synonym']['synonyms'] = get_synonyms(es_connection)
        es_connection.indices.create(index=index_name, body=index_settings)
        logger.info('...index [%s] created.', index_name)
        return index_name

    @classmethod
    def delete_index(cls, es_connection, index):
        logger.info('Deleting index [%s]...', index)
        es_connection.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        logger.info('...index deleted.')

    @classmethod
    def refresh_index(cls, es_connection, index):
        """
        Refreshes the index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        logger.info('Refreshing index [%s]...', index)
        es_connection.indices.refresh(index=index)
        es_connection.cluster.health(index=index, wait_for_status='yellow', request_timeout=1)
        logger.info('...index refreshed.')


def get_all_related_field_names(model):
    """
    Returns the names of all related fields (e.g. ForeignKey ManyToMany)

    Args:
        model (Model): Model whose field names should be returned

    Returns:
        list[str]
    """
    fields = model._meta._get_fields(forward=False)  # pylint: disable=protected-access
    names = set([field.name for field in fields])
    return list(names)


def delete_orphans(model):
    """
    Deletes all instances of the given model with no relationships to other models.

    Args:
        model (Model): Model whose instances should be deleted

    Returns:
        None
    """
    field_names = get_all_related_field_names(model)
    kwargs = {'{0}__isnull'.format(field_name): True for field_name in field_names}
    model.objects.filter(**kwargs).delete()
