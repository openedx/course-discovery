from django.apps import apps
from django.core.exceptions import FieldError
from django.core.serializers import json
from django.http.response import Http404, HttpResponse, HttpResponseForbidden

from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet
from course_discovery.apps.edx_catalog_extensions.api.serializers import DistinctCountsAggregateFacetSearchSerializer
from course_discovery.apps.edx_haystack_extensions.distinct_counts.query import DistinctCountsSearchQuerySet


class DistinctCountsAggregateSearchViewSet(AggregateSearchViewSet):
    """ Provides a facets action that can include distinct hit and facet counts in the response."""

    # Custom serializer that includes distinct hit and facet counts.
    facet_serializer_class = DistinctCountsAggregateFacetSearchSerializer

    def get_queryset(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """ Return the base Queryset to use to build up the search query."""
        queryset = super(DistinctCountsAggregateSearchViewSet, self).get_queryset(*args, **kwargs)
        return DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')


class Walker:
    def __init__(self, exclude=None):
        self.seen = set()
        self.exclude = set(exclude or [])

    def walk(self, *objs):
        for obj in objs:
            name = '{}.{}'.format(obj._meta.app_label, obj._meta.model_name)
            if name in self.exclude:
                continue
            key = (name, obj.pk)
            if key in self.seen:
                continue
            self.seen.add(key)
            for field in obj._meta.many_to_many:
                for oo in self.walk(*getattr(obj, field.name).all()):
                    yield oo
            for field in obj._meta.fields:
                if field.is_relation:
                    related_obj = getattr(obj, field.name, None)
                    if related_obj:
                        for oo in self.walk(related_obj):
                            yield oo
            yield obj


def get_fixture(request):
    """
    Returns a json fixture suitable for use with Django's loaddata command.

    For instance:
    /extensions/api/v1/fixture/?model=course_metadata.program&authoring_organizations__key=MITx
    will return all MITx programs and related objects (courses, courseruns, tags, etc.)
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    try:
        query_args = {}
        for key, value in request.GET.items():
            query_args[key] = value
        model_name = query_args.pop('model')
        model_object = apps.get_model(model_name).objects.filter(**query_args)
    except (KeyError, FieldError):
        raise Http404()
    serializer = json.Serializer()
    response = serializer.serialize(Walker(['sites.site', 'core.user', 'core.partner']).walk(*model_object))
    return HttpResponse(response, content_type='text/json')
