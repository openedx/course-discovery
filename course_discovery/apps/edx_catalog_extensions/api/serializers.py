# pylint: disable=abstract-method
from rest_framework import serializers
from rest_framework.fields import DictField

from course_discovery.apps.api.serializers import QueryFacetFieldSerializer
from course_discovery.apps.course_metadata.search_indexes.serializers.aggregation import AggregateFacetSearchSerializer
from course_discovery.apps.edx_haystack_extensions.serializers import (
    FacetDictField,
    FacetFieldSerializer,
    FacetListField,
)


class DistinctCountsAggregateFacetSearchSerializer(AggregateFacetSearchSerializer):
    """ Custom AggregateFacetSearchSerializer which includes distinct hit and facet counts."""

    def to_representation(self, instance):
        pres = super().to_representation(instance)
        return pres

    def get_fields(self):
        """ Return the field_mapping needed for serializing the data."""
        # Re-implement the logic from the superclass methods, but make sure to handle field and query facets properly.
        field_data = self.instance.pop('fields', {})
        query_data = self.format_query_facet_data(self.instance.pop('queries', {}))
        field_mapping = super().get_fields()

        field_mapping['fields'] = FacetDictField(
            child=FacetListField(child=DistinctCountsFacetFieldSerializer(field_data), required=False)
        )

        field_mapping['queries'] = DictField(
            query_data, child=DistinctCountsQueryFacetFieldSerializer(), required=False
        )

        if self.serialize_objects:
            field_mapping.move_to_end('objects')

        self.instance['fields'] = field_data
        self.instance['queries'] = query_data
        return field_mapping

    def get_objects(self, instance):
        """ Return the objects that should be serialized along with the facets."""
        data = super().get_objects(instance)
        data['distinct_count'] = self.context['objects'].distinct_count()
        return data

    def format_query_facet_data(self, query_facet_counts):
        """ Format and return the query facet data so that it may be properly serialized."""
        # Re-implement the logic from the superclass method, but make sure to handle changes to the raw query facet
        # data and extract the distinct counts.
        query_data = {}
        view = self.context["view"]
        for field, options in getattr(view, 'faceted_query_filter_fields', {}).items():
            # The query facet data is expected to be formatted as a dictionary with fields mapping to a two-tuple
            # containing count and distinct count.
            count, distinct_count = query_facet_counts.get(field, (0, 0))
            if count:
                query_data[field] = {
                    'field': field,
                    'options': options,
                    'count': count,
                    'distinct_count': distinct_count,
                }
        return query_data


class DistinctCountsFacetFieldSerializer(FacetFieldSerializer):
    """ Custom FacetFieldSerializer which includes distinct counts."""

    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        """ Return the distinct count for this facet."""
        # The instance is expected to be formatted as a three tuple containing the field name, normal count and
        # distinct count. This is consistent with the superclass implementation here:
        count = instance[2]
        return serializers.IntegerField(read_only=True).to_representation(count)


class DistinctCountsQueryFacetFieldSerializer(QueryFacetFieldSerializer):
    """ Custom QueryFacetFieldSerializer which includes distinct counts."""

    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        """ Return the distinct count for this facet."""
        count = instance['distinct_count']
        return serializers.IntegerField(read_only=True).to_representation(count)
