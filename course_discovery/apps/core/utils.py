import datetime
import logging

from django.conf import settings

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
            index_settings = settings.ELASTICSEARCH_INDEX_SETTINGS
            es.indices.create(index=index, body=index_settings)
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
