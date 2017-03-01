from drf_haystack.fields import FacetDictField, FacetListField
from drf_haystack.serializers import FacetFieldSerializer
from rest_framework import serializers
from rest_framework.fields import DictField

from course_discovery.apps.api.serializers import AggregateFacetSearchSerializer, QueryFacetFieldSerializer


class DistinctCountsAggregateFacetSearchSerializer(AggregateFacetSearchSerializer):
    """
    Custom AggregateFacetSearchSerializer which includes distinct hit and facet counts.
    
    This serializer is only expected to be used when we need to compute distinct hit and facet counts.
    It is expected to be configured with an instance of our custom DistinctCountsSearchQuerySet class.
    Configuring it with a normal SearchQuerySet object will result in an error.
    """

    def get_fields(self):
        """
        Return the field_mapping needed for serializing the data.

        Overrides and re-implements BaseHaystackFacetSerializer.get_fields so that the correct facet serializer
        classes may be specified for each facet type.
        """
        field_data = self.instance.pop('fields', {})
        query_data = self.format_query_facet_data(self.instance.pop('queries', {}))
        field_mapping = super(DistinctCountsAggregateFacetSearchSerializer, self).get_fields()

        # Use our custom DistinctCountsFacetFieldSerializer, which includes distinct counts, to serialize
        # field facets.
        field_mapping['fields'] = FacetDictField(
            child=FacetListField(child=DistinctCountsFacetFieldSerializer(field_data), required=False)
        )

        # Use our custom DistinctCountsQueryFacetFieldSerializer, which includes distinct counts, to serialize
        # field facets.
        field_mapping['queries'] = DictField(
            query_data, child=DistinctCountsQueryFacetFieldSerializer(), required=False
        )

        if self.serialize_objects:
            field_mapping.move_to_end('objects')

        self.instance['fields'] = field_data
        self.instance['queries'] = query_data

        return field_mapping

    def get_objects(self, instance):
        """
        Return the objects that should be serialized along with the facets.

        Overrides HaystackFacetSerializer.get_objects so that the distinct hit count may be added
        to the result.
        """
        data = super(DistinctCountsAggregateFacetSearchSerializer, self).get_objects(instance)

        # This serializer is only expected to be used when we need to compute distinct counts.
        # Therefore, context['objects'] is expected to be an instance of our custom 
        # DistinctCountsSearchQuerySet class, which exposes a distinct_count method.
        data['distinct_count'] = self.context['objects'].distinct_count()
        return data

    def format_query_facet_data(self, query_facet_counts):
        """
        Format and return the query facet data so that it may be properly serialized.

        Re-implements BaseHaystackFacetSerializer.format_query_facet_data so that distinct
        count information may be included with the data.
        """
        query_data = {}
        for field, options in getattr(self.Meta, 'field_queries', {}).items():  # pylint: disable=no-member
            # This serializer is only expected to be used when we need to compute distinct counts.
            # The custom DistinctCountstSearchQuery backend formats query facet counts as a dictionary
            # with field_name mapping to a two tuple containing normal count and distinct count.
            counts = query_facet_counts.get(field, (0, 0))
            if counts[0]:
                query_data[field] = {
                    'field': field,
                    'options': options,
                    'count': counts[0],
                    'distinct_count': counts[1],
                }
        return query_data


class DistinctCountsFacetFieldSerializer(FacetFieldSerializer):
    """
    Custom FacetFieldSerializer which includes distinct counts.
    
    This serializer is only expected to be used by the DistinctCountsAggregateFacetSearchSerializer, when
    we need to compute distinct hit and facet counts.
    """
    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        """Return the distinct count for this facet."""

        # The DistinctCountsElasticsearchBackendWrapper formats field facet counts as a three tuple
        # containing the field name, normal count and distinct count.
        count = instance[2]
        return serializers.IntegerField(read_only=True).to_representation(count)


class DistinctCountsQueryFacetFieldSerializer(QueryFacetFieldSerializer):
    """
    Custom QueryFacetFieldSerializer which includes distinct counts.
    
    This serializer is only expected to be used by the DistinctCountsAggregateFacetSearchSerializer, when
    we need to compute distinct hit and facet counts.
    """
    distinct_count = serializers.SerializerMethodField()

    def get_distinct_count(self, instance):
        """Return the distinct count for this facet."""
        count = instance['distinct_count']
        return serializers.IntegerField(read_only=True).to_representation(count)
