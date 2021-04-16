from traceback import format_exc

from django.core.exceptions import ObjectDoesNotExist
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.api.utils import gen_error_response
from course_discovery.apps.course_metadata.models import Program, Course


# pylint: disable=no-member
class ProgramViewSet(CacheResponseMixin, viewsets.ModelViewSet):
    """Program resource

    """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.ProgramFilter

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_serializer_class(self, hit_courses_endpoint=False):
        """Return serializer class by conditions

            Args:
                hit_courses_endpoint:   True,  endpoint is ended with`courses`
                                        False, endpoint is not ended with `courses`

            Returns:
                Return the serializer class by `actions` and `hit_courses_endpoint`

            Raises:
                Null
        """
        # Endpoint:
        #   - api/v1/programs/
        #   - api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/
        #   - api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/
        if not hit_courses_endpoint:
            if 'list' == self.action:
                return serializers.MinimalProgramSerializer
            elif self.action in ('partial_update', 'update', 'create'):
                return serializers.LearningTribeProgramSerializer

        return serializers.ProgramSerializer

    def get_queryset(self, hit_courses_endpoint=False, *args, **kwargs):
        # This method prevents prefetches on the program queryset from "stacking,"
        # which happens when the queryset is stored in a class property.
        serializer_class = self.get_serializer_class(
            hit_courses_endpoint=hit_courses_endpoint
        )

        if not hit_courses_endpoint:    # Endpoint: programs/
            return serializer_class.prefetch_queryset(partner=self.request.site.partner)
        else:                           # Endpoint: courses/
            return serializer_class.prefetch_queryset(
                partner=self.request.site.partner,
                program_uuid=self.kwargs[self.lookup_field]
            )

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        query_params = ['exclude_utm', 'use_full_course_serializer', 'published_course_runs_only',
                        'marketable_enrollable_course_runs_with_archived']
        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        return context

    def list(self, request, *args, **kwargs):
        """ List all programs.

            Endpoint: api/v1/programs/

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
            queryset = self.filter_queryset(Program.objects.filter(partner=self.request.site.partner))
            uuids = queryset.values_list('uuid', flat=True)

            return Response(uuids)

        return super(ProgramViewSet, self).list(request, *args, **kwargs)

    @detail_route(methods=['get', 'post', 'delete'], permission_classes=[IsAuthenticated])
    def courses(self, request, uuid):
        """Endpoint handler of `api/v1/programs/{program_uuid}/courses/`

            GET:    list courses for a Program UUID
            POST:   add a new course (course_uuid) into a program
            DELETE: delete a course from a program
        """
        try:
            course_uuid = self.request.data.get('course_uuid')
            programs = self.get_queryset(hit_courses_endpoint=True)

            if request.method == 'GET':
                serializer = self.get_serializer_class(hit_courses_endpoint=True)(
                    programs, many=True, context={'request': self.request}
                )

                return Response(serializer.data[0]['courses'], status=status.HTTP_200_OK)
            elif request.method == 'POST':
                course = Course.objects.get(uuid=course_uuid)
                programs[0].courses.add(course)
                # After adding a new course into Program:
                #   make sure to update all the Program Team Member are all in this new Course's Team.
                # TO DO: POST: (course_id, program_uuid) to lms rest api for updating
                return Response({'course_uuid': course.uuid}, status=status.HTTP_201_CREATED)
            else:  # DELETE
                course = Course.objects.get(uuid=course_uuid)
                programs[0].courses.remove(course)

                return Response({'course_uuid': course.uuid}, status=status.HTTP_200_OK)
        except Exception as e:
            return gen_error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR, str(e), format_exc()
            )
