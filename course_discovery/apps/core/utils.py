import datetime
import logging

from django.conf import settings

from course_discovery.settings.process_synonyms import get_synonyms

logger = logging.getLogger(__name__)


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


class SearchQuerySetWrapper(object):
    """
    Decorates a SearchQuerySet object using a generator for efficient iteration
    """
    def __init__(self, qs):
        self.qs = qs

    def __getattr__(self, item):
        try:
            super().__getattr__(item)
        except AttributeError:
            # If the attribute is not found on this class,
            # proxy the request to the SearchQuerySet.
            return getattr(self.qs, item)

    def __iter__(self):
        for result in self.qs:
            yield result.object

    def __getitem__(self, key):
        if isinstance(key, int) and (key >= 0 or key < self.count()):
            # return the object at the specified position
            return self.qs[key].object
        # Pass the slice/range on to the delegate
        return SearchQuerySetWrapper(self.qs[key])
