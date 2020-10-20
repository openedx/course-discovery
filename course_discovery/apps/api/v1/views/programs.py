import base64

from django.core.files.base import ContentFile
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_framework_filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.course_metadata.models import Program


class ProgramViewSet(CompressedCacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Program resource. """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, rest_framework_filters.OrderingFilter)
    filterset_class = filters.ProgramFilter

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
        partner = self.request.site.partner
        q = self.request.query_params.get('q')
        queryset = None

        if q:
            queryset = Program.search(q)

        return self.get_serializer_class().prefetch_queryset(queryset=queryset, partner=partner)

    def get_serializer_context(self):
        context = super().get_serializer_context()
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
            - name: q
              description: Elasticsearch querystring query. This filter takes precedence over other filters
              required: false
              type: string
              paramType: query
              multiple: false
        """
        if get_query_param(self.request, 'uuids_only'):
            # DRF serializers don't have good support for simple, flat
            # representations like the one we want here.
            queryset = self.filter_queryset(Program.objects.filter(partner=self.request.site.partner))
            uuids = queryset.values_list('uuid', flat=True)

            return Response(uuids)

        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def update_card_image(self, request, *_args, **_kwargs):
        if not self.request.user.is_staff:
            raise PermissionDenied
        program = self.get_object()
        image_data = request.data.get('image', None)
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            # base64 encoded image - decode
            file_format, imgstr = image_data.split(';base64,')  # format ~= data:image/X;base64,/xxxyyyzzz/
            ext = file_format.split('/')[-1]  # guess file extension
            image_data = ContentFile(base64.b64decode(imgstr), name=f'tmp.{ext}')
            program.card_image.save(image_data.name, image_data)
            msg = 'Successfully updated program card image for program {uuid}: {title}'.format(uuid=program.uuid,
                                                                                               title=program.title)
            return Response(msg)
        else:
            return Response('Bad image data in request', status=status.HTTP_400_BAD_REQUEST)
