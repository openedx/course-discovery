"""
Filters for the Learner Pathway APIs.
"""

from django_filters import rest_framework as filters

from course_discovery.apps.learner_pathway.models import LearnerPathway


class PathwayUUIDFilter(filters.FilterSet):
    """
    Filter pathways by uuid. Supports filtering by comma-delimited list of uuids.
    """
    uuid = filters.CharFilter(method='filter_by_uuid')

    class Meta:
        model = LearnerPathway
        fields = ['uuid']

    def filter_by_uuid(self, queryset, name, value):  # pylint: disable=unused-argument
        uuid_values = value.strip().split(',')
        return queryset.filter(uuid__in=uuid_values)
