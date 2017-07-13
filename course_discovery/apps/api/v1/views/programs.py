from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.course_metadata.models import Program


# pylint: disable=no-member
class ProgramViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Program resource. """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.ProgramFilter

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.MinimalProgramSerializer

        return serializers.ProgramSerializer

    def get_queryset(self):
        # This method prevents prefetches on the program queryset from "stacking,"
        # which happens when the queryset is stored in a class property.
        return self.get_serializer_class().prefetch_queryset()

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        query_params = ['exclude_utm', 'use_full_course_serializer', 'published_course_runs_only',
                        'marketable_enrollable_course_runs_with_archived']
        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        return context

    def list(self, request, *args, **kwargs):
        """ List all programs.
        ---
        parameters:
            - name: marketable
              description: Retrieve marketable programs. A program is considered marketable if it is active
                and has a marketing slug.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: published_course_runs_only
              description: Filter course runs by published ones only
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: marketable_enrollable_course_runs_with_archived
              description: Restrict returned course runs to those that are published, have seats,
                and can be enrolled in now. Includes archived courses.
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: use_full_course_serializer
              description: Return all serialized course information instead of a minimal amount of information.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: types
              description: Filter by comma-separated list of program type slugs
              required: false
              type: string
              paramType: query
              multiple: false
        """
        if get_query_param(self.request, 'uuids_only'):
            # DRF serializers don't have good support for simple, flat
            # representations like the one we want here.
            queryset = self.filter_queryset(Program.objects.all())
            uuids = queryset.values_list('uuid', flat=True)

            return Response(uuids)

        return super(ProgramViewSet, self).list(request, *args, **kwargs)
