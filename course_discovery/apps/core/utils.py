import datetime
import logging
import re
from collections import namedtuple

from django.conf import settings
from django.db.models import prefetch_related_objects
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
    def update_max_result_window(cls, connection, max_result_window, index):
        if connection.indices.exists(index=index):
            connection.indices.put_settings(index=index, body={"index": {"max_result_window": max_result_window}})

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

    def __init__(self, queryset, model):
        # This is necessary to act like Django ORM Queryset
        self.model = model

        self.queryset = queryset
        self._select_related_lookups = ()
        self._prefetch_related_lookups = ()

    def prefetch_related(self, *lookups):
        """Same as QuerySet.prefetch_related()"""
        clone = self._chain()
        if not lookups or lookups == (None,):
            clone._prefetch_related_lookups = ()  # pylint: disable=protected-access
        else:
            clone._prefetch_related_lookups += lookups
        return clone

    def select_related(self, *lookups):
        """Will work same as .prefetch_related()"""
        clone = self._chain()
        if not lookups or lookups == (None,):
            clone._select_related_lookups = ()  # pylint: disable=protected-access
        else:
            clone._select_related_lookups += lookups
        return clone

    def _chain(self):
        clone = self.__class__(queryset=self.queryset, model=self.model)
        clone._select_related_lookups = self._select_related_lookups  # pylint: disable=protected-access
        clone._prefetch_related_lookups = self._prefetch_related_lookups  # pylint: disable=protected-access
        return clone

    def __getattr__(self, item):
        # If the attribute is not found on this class,
        # proxy the request to the SearchQuerySet.
        return getattr(self.queryset, item)

    def __iter__(self):
        results = [r.object for r in self.queryset]

        # Both select_related & prefetch_related will act as prefetch_related
        prefetch_lookups = set(self._select_related_lookups) | set(self._prefetch_related_lookups)
        if prefetch_lookups:
            prefetch_related_objects(results, *prefetch_lookups)

        yield from results

    def __getitem__(self, key):
        single_value = isinstance(key, int)

        clone = self._chain()
        clone.queryset = self.queryset[slice(key, key + 1) if single_value else key]

        if single_value:
            return list(clone)[0]

        return clone


def use_read_replica_if_available(queryset):
    """
    If there is a database called 'read_replica', use that database for the queryset.
    """
    return queryset.using("read_replica") if "read_replica" in settings.DATABASES else queryset


def update_instance(instance, data, should_commit=False, **kwargs):
    """
    Utility method to set any number of fields dynamically on a model instance and commit the changes
    if applicable.

    Arguments:
        * instance (Model Object)
        * data (dict): The dictionary containing mapping of model_fields -> values. The fields are not related fields.
        * should_commit (Boolean): If provided, the changes in instance should be committed to DB
        * kwargs (dict): additional params to pass to save() if provided

    Return:
        Tuple containing instance and boolean specify if the instance was updated.
    """
    if not instance:
        return None, False

    updated = False

    for attr, value in data.items():
        if hasattr(instance, attr) and getattr(instance, attr) != value:
            setattr(instance, attr, value)
            updated = True

    if updated and should_commit:
        instance.save(**kwargs)

    return instance, updated
