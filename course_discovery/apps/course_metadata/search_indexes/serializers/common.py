import logging

from django.core.exceptions import ObjectDoesNotExist
from django_elasticsearch_dsl.registries import registry

from course_discovery.apps.core.utils import ElasticsearchUtils

log = logging.getLogger(__name__)


class ModelObjectDocumentSerializerMixin:
    """
    Model object document serializer mixin.

    This mixin can be added to provide db model interface for elasticsearch response.
    There is method `get_model_object_by_instance` to fetch Model object.
    """

    def get_model_object_by_instance(self, instance):
        """
        Provide Model object by elasticsearch response instance.
        """
        document = None
        _object = None
        index_or_alias_name = ElasticsearchUtils.get_alias_by_index_name(instance.meta.index)
        for doc in registry.get_documents():
            if index_or_alias_name == doc._index._name:  # pylint: disable=protected-access
                document = doc
                break
        hit = self._build_hit(instance)
        es_pk = hit['_source'].get('pk')
        if document and es_pk:
            try:
                _object = document(hit).get_queryset().get(pk=es_pk)
            except ObjectDoesNotExist:
                log.error("Object could not be found in database for SearchResult '%r'.", self)

        return _object

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
        _object = self.get_model_object_by_instance(instance)
        return super(DocumentDSLSerializerMixin, self).to_representation(_object)
