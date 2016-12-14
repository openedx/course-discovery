from rest_framework import mixins, viewsets
from rest_framework.filters import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.v1.views import get_query_param
from course_discovery.apps.course_metadata.models import ProgramType


# pylint: disable=no-member
class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """ Program resource. """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.ProgramFilter

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
        context.update({
            'published_course_runs_only': get_query_param(self.request, 'published_course_runs_only'),
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all programs.
        ---
        parameters:
            - name: partner
              description: Filter by partner
              required: false
              type: string
              paramType: query
              multiple: false
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
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        return super(ProgramViewSet, self).list(request, *args, **kwargs)


class ProgramTypeListViewSet(mixins.ListModelMixin,
                             viewsets.GenericViewSet):
    """ ProgramType resource. """
    serializer_class = serializers.ProgramTypeSerializer
    permission_classes = (IsAuthenticated,)
    queryset = ProgramType.objects.all()
