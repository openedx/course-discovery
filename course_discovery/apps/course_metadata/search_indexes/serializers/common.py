import logging

from django.core.exceptions import ObjectDoesNotExist
from django.utils.dateparse import parse_datetime
from django_elasticsearch_dsl.registries import registry

from course_discovery.apps.api.utils import get_excluded_restriction_types
from course_discovery.apps.core.utils import ElasticsearchUtils, serialize_datetime

log = logging.getLogger(__name__)


class DateTimeSerializerMixin:
    @staticmethod
    def handle_datetime_field(value):
        if isinstance(value, str):
            value = parse_datetime(value)
        return serialize_datetime(value)


class ModelObjectDocumentSerializerMixin:
    """
    Model object document serializer mixin.

    This mixin can be added to provide db model interface for elasticsearch response.
    There is method `get_model_object_by_instances` to fetch Model object.
    """

    def get_model_object_by_instances(self, instances):
        """
        Provide Model objects by elasticsearch response instances.
        Fetches all the incoming instances at once and returns model queryset.
        """

        excluded_restriction_types = get_excluded_restriction_types(self.context['request'])

        if not isinstance(instances, list):
            instances = [instances]
        document = None
        _objects = []
        index_or_alias_name = ElasticsearchUtils.get_alias_by_index_name(instances[0].meta.index)
        for doc in registry.get_documents():
            if index_or_alias_name == doc._index._name:  # pylint: disable=protected-access
                document = doc
                break

        es_pks = []
        for instance in instances:
            es_pks.append(instance.pk)

        hit = self._build_hit(instances[0])

        if document and es_pks:
            try:
                _objects = document(hit).get_queryset(
                    excluded_restriction_types=excluded_restriction_types
                ).filter(pk__in=es_pks)
            except ObjectDoesNotExist:
                log.error("Object could not be found in database for SearchResult '%r'.", self)

        return _objects

    @staticmethod
    def _build_hit(instance):
        return {
            '_id': instance.meta.id,
            '_index': instance.meta.index,
            '_score': instance.meta.score,
            '_source': instance.to_dict(),
            '_type': instance.meta.doc_type,
        }


class DocumentDSLSerializerMixin(ModelObjectDocumentSerializerMixin):
    """
    Document elasticsearch dsl serializer mixin.

    This mixin can be added to a serializer to use the actual object
    as the data source for serialization rather
    than the data stored in the search index fields.
    This makes it easy to return data from search results in
    the same format as elsewhere in your API and reuse your existing serializers
    """

    def to_representation(self, instance):
        _object = self.get_model_object_by_instances(instance).get()
        return super().to_representation(_object)
