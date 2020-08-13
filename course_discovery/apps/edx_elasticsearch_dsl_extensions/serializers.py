import datetime
from collections import OrderedDict

from django.core.exceptions import ImproperlyConfigured
from django_elasticsearch_dsl import Document
from rest_framework import serializers
from rest_framework.fields import DictField, ListField

from course_discovery.apps.api.serializers import QueryFacetFieldSerializer


# pylint: disable=abstract-method
class FacetFieldSerializer(serializers.Serializer):
    """
    Responsible for serializing a faceted result.

    Note: Implemented to be backward compatible with previous used drf-haystack lib.
    """

    text = serializers.SerializerMethodField()
    count = serializers.SerializerMethodField()
    narrow_url = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        self._parent_field = None
        super().__init__(*args, **kwargs)

    @property
    def parent_field(self):
        return self._parent_field

    @parent_field.setter
    def parent_field(self, value):
        self._parent_field = value

    def get_paginate_by_param(self):
        """
        Returns the `paginate_by_param` for the (root) view paginator class.
        This is needed in order to remove the query parameter from faceted
        narrow urls.

        If using a custom pagination class, this class attribute needs to
        be set manually.
        """
        if hasattr(self.root, 'paginate_by_param') and self.root.paginate_by_param:
            return self.root.paginate_by_param

        pagination_class = self.context['view'].pagination_class
        if not pagination_class:
            return None

        if hasattr(pagination_class, 'page_query_param'):
            return pagination_class.page_query_param

        elif hasattr(pagination_class, 'offset_query_param'):
            return pagination_class.offset_query_param

        elif hasattr(pagination_class, 'cursor_query_param'):
            return pagination_class.cursor_query_param

        else:
            raise AttributeError(
                '%(root_cls)s is missing a `paginate_by_param` attribute. '
                'Define a %(root_cls)s.paginate_by_param or override '
                '%(cls)s.get_paginate_by_param().'
                % {'root_cls': self.root.__class__.__name__, 'cls': self.__class__.__name__}
            )

    def get_text(self, instance):
        """
        Facets are returned as a two-tuple (value, count).
        The text field should contain the faceted value.
        """
        instance = instance[0]
        if isinstance(instance, str):
            return serializers.CharField(read_only=True).to_representation(instance)
        elif isinstance(instance, datetime.datetime):
            return serializers.DateTimeField(read_only=True).to_representation(instance)
        return instance

    def get_count(self, instance):
        """
        Facets are returned as a two-tuple (value, count).
        The count field should contain the faceted count.
        """
        instance = instance[1]
        return serializers.IntegerField(read_only=True).to_representation(instance)

    def get_narrow_url(self, instance):
        """
        Return a link suitable for narrowing on the current item.
        """
        text = instance[0]
        request = self.context['request']
        query_params = request.GET.copy()

        # Never keep the page query parameter in narrowing urls.
        # It will raise a NotFound exception when trying to paginate a narrowed queryset.
        page_query_param = self.get_paginate_by_param()
        if page_query_param and page_query_param in query_params:
            del query_params[page_query_param]

        selected_facets = set(query_params.pop(self.root.facet_query_params_text, []))
        selected_facets.add('%(field)s_exact:%(text)s' % {'field': self.parent_field, 'text': text})
        query_params.setlist(self.root.facet_query_params_text, sorted(selected_facets))

        path = '%(path)s?%(query)s' % {'path': request.path_info, 'query': query_params.urlencode()}
        url = request.build_absolute_uri(path)
        return serializers.Hyperlink(url, 'narrow-url')

    # pylint: disable=arguments-differ
    def to_representation(self, field, instance):
        """
        Set the `parent_field` property equal to the current field on the serializer class,
        so that each field can query it to see what kind of attribute they are processing.
        """
        self.parent_field = field
        return super(FacetFieldSerializer, self).to_representation(instance)


class FacetDictField(DictField):
    """
    A special DictField which passes the key attribute down to the children's
    `to_representation()` in order to let the serializer know what field they're
    currently processing.

    Note: Implemented to be backward compatible with previous used drf-haystack lib.
    """

    def to_representation(self, value):
        return {key: self.child.to_representation(key, val) for key, val in value.items()}


class FacetListField(ListField):
    """
    The `FacetListField` just pass along the key derived from
    `FacetDictField`.

    Note: Implemented to be backward compatible with previous used drf-haystack lib.
    """

    # pylint: disable=arguments-differ
    def to_representation(self, key, data):
        return [self.child.to_representation(key, item) for item in data]


# pylint: disable=abstract-method
class DjangoESDSLDRFFacetSerializer(serializers.Serializer):
    """
    The `DjangoESDSLDRFFacetSerializer` is used to serialize the facets
    dictionary results on a `Search` instance.

    Note: Implemented to be backward compatible with previous used drf-haystack lib.
    """

    _abstract = True
    serialize_objects = False
    paginate_by_param = None
    facet_dict_field_class = FacetDictField
    facet_list_field_class = FacetListField
    facet_field_serializer_class = FacetFieldSerializer

    def to_representation(self, instance):
        res = super().to_representation(instance)
        return res

    def get_fields(self):
        """
        This returns a dictionary containing the top most fields,
        `dates`, `fields` and `queries`.
        """
        field_mapping = OrderedDict()
        for field, data in self.instance.items():
            field_mapping.update(
                {
                    field: self.facet_dict_field_class(
                        child=self.facet_list_field_class(child=self.facet_field_serializer_class(data)), required=False
                    )
                }
            )
        if self.serialize_objects is True:
            field_mapping['objects'] = serializers.SerializerMethodField()
        return field_mapping

    # pylint: disable=unused-argument
    def get_objects(self, instance):
        """
        Return a list of objects matching the faceted result.
        """
        view = self.context['view']
        queryset = self.context['objects']

        page = view.paginate_queryset(queryset)
        if page is not None:
            serializer = view.get_facet_objects_serializer(page, many=True)
            return OrderedDict(
                [
                    ('count', self.get_count(queryset)),
                    ('next', view.paginator.get_next_link()),
                    ('previous', view.paginator.get_previous_link()),
                    ('results', serializer.data),
                ]
            )

        serializer = view.get_serializer(queryset, many=True)
        return serializer.data

    def get_count(self, queryset):
        """
        Determine an object count, supporting either querysets or regular lists.
        """
        try:
            return queryset.count()
        except (AttributeError, TypeError):
            return len(queryset)

    @property
    def facet_query_params_text(self):
        return self.context['facet_query_params_text']


# pylint: disable=abstract-method
class BaseDjangoESDSLFacetSerializer(DjangoESDSLDRFFacetSerializer):
    _abstract = True
    serialize_objects = True

    def get_fields(self):
        query_facet_counts = self.instance.pop('queries', {})

        field_mapping = super(BaseDjangoESDSLFacetSerializer, self).get_fields()

        query_data = self.format_query_facet_data(query_facet_counts)

        field_mapping['queries'] = DictField(query_data, child=QueryFacetFieldSerializer(), required=False)

        if self.serialize_objects:
            field_mapping.move_to_end('objects')

        self.instance['queries'] = query_data

        return field_mapping

    def format_query_facet_data(self, query_facet_counts):
        query_data = {}
        view = self.context['view']
        for field, options in getattr(view, 'faceted_query_filter_fields', {}).items():
            count = query_facet_counts.get(field, 0)
            if count:
                query_data[field] = {'field': field, 'options': options, 'count': count}
        return query_data


class DummyModel:
    """
    Dummy model.

    Implementation of the minimum required functionality of the model
    so that it can be used in the django-elasticsearch-dsl document.
    """

    def __init__(self):
        self._meta = object()
        setattr(self._meta, 'get_fields', lambda self: [])  # pylint: disable=literal-used-as-attribute


class DummyDocument(Document):
    """
    Dummy django-elasticsearch-dsl document.

    Implementation of the minimum required functionality of the document
    so that it can be used in the django-drf serializer.
    """

    _fields = {}

    class Django:
        model = DummyModel


class MultiDocumentSerializerMixin:
    """
    Multi document serializer mixin.

    Used to serialize the results of an aggregated search where,
    several indexes are used at the same time.
    """

    def to_representation(self, instance):
        """
        If we have a serializer mapping, use that.  Otherwise, use standard serializer behavior
        Since we might be dealing with multiple indexes, some fields might
        not be valid for all results. Do not render the fields which don't belong
        to the search result.
        """
        if self.Meta.serializers:
            representation = self.multi_serializer_representation(instance)
        else:
            representation = super().to_representation(instance)

        return representation

    def multi_serializer_representation(self, instance):
        """
        Multi serializer representation.
        """
        # pylint: disable=protected-access
        instance_serializers = {
            document._index._name: serializer for document, serializer in self.Meta.serializers.items()
        }
        index = instance.meta['index']
        serializer_class = instance_serializers.get(index, None)
        if not serializer_class:
            raise ImproperlyConfigured('Could not find serializer for %s in mapping' % index)
        return serializer_class(context=self._context).to_representation(instance)
