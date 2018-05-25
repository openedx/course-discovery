from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.api import filters, serializers


class DigitalBookBundleViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Digital Book Bundle resource """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    #TODO: figure out what filters are appropriate
    # filter_class

    #TODO: what pagination should i support
    #pagination_class

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.MinimalDigitalBookBundleSerializer

        # TODO: should this be something different? what is the difference between these two classes?!?
        return serializers.MinimalDigitalBookBundleSerializer

    def get_queryset(self):
        # This method prevents prefetches on the digital book bundle queryset from "stacking"
        # which happens when the queryset is stored in a class property
        #TODO: should deals be asscoriated with partners?
        return self.get_serializer_class().prefetch_queryset()

