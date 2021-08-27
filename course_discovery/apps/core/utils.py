import datetime
import logging
import re
from collections import namedtuple

from django.conf import settings
from django_elasticsearch_dsl import Index

IndexMeta = namedtuple("IndexMeta", "name alias")
logger = logging.getLogger(__name__)

INDEX_ALIAS_REGEX = re.compile(r'^(\w+)(?=[_]\d{8}[_]\d{6})')
INDEX_ALIAS_SLICE = slice(0, -16)
# Any elasticsearch index name for a django model has two parts:
# Part 1 - title. The name is the same as the model name and will henceforth be an alias for this index.
# Part 2 - timestamp (time of index creation). The format is `%Y%m%d_%H%M%S`, i.e. 20200826_122240
# For example, for the CourseRun model, the index will be named course_run_20200826_122240.
# To get 1 part, i.e. the alias needs to be subtracted from the timestamp. So
# >>> 'course_run_20200826_122240'[INDEX_ALIAS_SLICE]
# >>> 'course_run'


def serialize_datetime(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ') if d else None


class ElasticsearchUtils:

    @staticmethod
    def get_alias_by_index_name(name):
        return name[INDEX_ALIAS_SLICE] if INDEX_ALIAS_REGEX.match(name) else name

    @classmethod
    def create_alias_and_index(cls, es_connection, index, conn_name='default'):
        assert isinstance(index, Index), '`index` must be an instance of `Index` class. Got: {}'.format(type(index))
        # pylint: disable=protected-access
        logger.info('Making sure alias [%s] exists...', index._name)
        alias = cls.get_alias_by_index_name(index._name)
        if es_connection.indices.exists_alias(name=alias):
            # If the alias exists, and points to an open index, we are all set.
            logger.info('...alias exists.')
        else:
            index, __ = cls.create_index(index, conn_name)
            # Point the alias to the new index
            cls.set_alias(es_connection, alias, index)
            logger.info('...alias updated.')

    @classmethod
    def set_alias(cls, connection, alias, index):
        """
        Points the alias to the specified index.

        All other references made by the alias will be removed, however the referenced indexes will
        not be modified in any other manner.

        Args:
            connection (ElasticsearchSearchBackend): Elasticsearch backend with an open connection.
            alias (str): Name of the alias to set.
            index (str): Name of the index where the alias should point.

        Returns:
            None
        """
        body = {
            'actions': [
                {"remove": {"alias": alias, "index": f'{alias}_*'}},
                {"add": {"alias": alias, "index": index}}
            ]
        }

        connection.indices.update_aliases(body)

    @classmethod
    def create_index(cls, index, conn_name='default'):
        """
        Creates a new index whose name is prefixed with the specified value.

        Args:
             index (Index): instance of `Index` class
             conn_name (str): Elasticsearch connection name

        Returns:
            IndexMeta (tuple): Name and generated alias of the new index.
        """
        assert isinstance(index, Index), '`index` must be an instance of `Index` class. Got: {}'.format(type(index))

        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        # pylint: disable=protected-access
        alias = cls.get_alias_by_index_name(index._name)
        index_name = f'{alias}_{timestamp}'
        index._name = index_name
        index.create(using=conn_name)
        index._name = alias
        return IndexMeta(index_name, alias)

    @classmethod
    def delete_index(cls, es_connection, index):
        logger.info('Deleting index [%s]...', index)
        es_connection.indices.delete(index=index, ignore=404)
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
    names = {field.name for field in fields}
    return list(names)


def delete_orphans(model, exclude=None):
    """
    Deletes all instances of the given model with no relationships to other models.

    Args:
        model (Model): Model whose instances should be deleted
        exclude: ID's of records to exclude from deletion

    Returns:
        None
    """
    field_names = get_all_related_field_names(model)
    kwargs = {f'{field_name}__isnull'.format(): True for field_name in field_names}
    query = model.objects.filter(**kwargs)
    if exclude:
        query = query.exclude(pk__in=exclude)

    query.delete()


class SearchQuerySetWrapper:
    """
    Decorates a SearchQuerySet object using a generator for efficient iteration
    """

    def __init__(self, qs):
        self.qs = qs

    def __getattr__(self, item):
        try:
            return super().__getattr__(item)
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
            return self.qs[key].execute()[0].object
        # Pass the slice/range on to the delegate
        return SearchQuerySetWrapper(self.qs[key])


def use_read_replica_if_available(queryset):
    """
    If there is a database called 'read_replica', use that database for the queryset.
    """
    return queryset.using("read_replica") if "read_replica" in settings.DATABASES else queryset
