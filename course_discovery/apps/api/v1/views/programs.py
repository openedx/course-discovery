from collections import OrderedDict
from traceback import format_exc

from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError
from django.db import connection
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.models import Program, ProgramType
from course_discovery.apps.core.models import Partner


class ProgramViewSet(CacheResponseMixin, viewsets.ModelViewSet):
    """Program resource

        Supported Endpoint:
          - api/v1/programs/
          - api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/
          - api/v1/programs/b6ca79cf0b5f408ea999e8c0589be5b0/courses/
    """
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)
    filter_class = filters.ProgramFilter

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_serializer_class(self):
        """Return serializer class by conditions"""
        if self.action in ('list', 'courses'):
            return serializers.MinimalProgramSerializer

        # actions: partial_update, update, create, retrieve, delete
        return serializers.ProgramSerializer

    def get_queryset(self):
        # This method prevents prefetches on the program queryset from "stacking,"
        # which happens when the queryset is stored in a class property.
        serializer_class = self.get_serializer_class()

        filters = {'partner': self.request.site.partner}
        program_uuid = self.kwargs.get(self.lookup_field)
        if program_uuid:
            filters['uuid'] = program_uuid

        return serializer_class.prefetch_queryset(**filters)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        query_params = ['exclude_utm', 'use_full_course_serializer', 'published_course_runs_only',
                        'marketable_enrollable_course_runs_with_archived']
        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        return context

    def create(self, request, *args, **kwargs):
        input_data = OrderedDict(request.data)

        if r'type' in input_data:
            input_data[r'type'] = ProgramType.objects.get(name=input_data[r'type'])
        if r'partner' in input_data:
            input_data[r'partner'] = Partner.objects.get(name=input_data[r'partner'])

        program_writer = self.get_serializer_class()  # ProgramSerializer
        writer = program_writer(data=input_data)
        if not writer.is_valid():
            raise ValidationError(
                'invalid arguments: {} \n fields error: {}'.format(
                    kwargs, writer.errors
                )
            )
        program_uuid = writer.save().uuid

        return Response(
            {'program_uuid': program_uuid}, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        input_data = OrderedDict(request.data)

        if r'type' in input_data:
            input_data[r'type'] = ProgramType.objects.get(name=input_data[r'type'])
        if r'partner' in input_data:
            input_data[r'partner'] = Partner.objects.get(name=input_data[r'partner'])

        program = self.get_object()
        writer = self.get_serializer(program, data=input_data, partial=True)
        if not writer.is_valid():
            raise ValidationError(
                'invalid arguments: {} \n fields error: {}'.format(
                    kwargs, writer.errors
                )
            )
        writer.save()

        return Response(
            {'program_uuid': program.uuid}, status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        program_uuid = kwargs['uuid']
        Program.objects.get(uuid=program_uuid).delete()

        return Response({'program_uuid': program_uuid}, status=status.HTTP_200_OK)

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


class ProgramCoursesViewSet(CacheResponseMixin, viewsets.ModelViewSet):
    lookup_field = 'uuid'

    def get_serializer_class(self):
        return serializers.MinimalProgramSerializer

    def get_queryset(self):
        filters = {
            'partner': self.request.site.partner,
            'program_uuid': self.kwargs['program_uuid']
        }

        return self.get_serializer_class().prefetch_queryset(**filters)

    def list(self, request, program_uuid):
        program = self.get_queryset().first()

        serializer = self.get_serializer(
            program, many=False, context={'request': self.request}
        )
        return Response(
            serializer.data['courses'], status=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        course_uuid = self.request.data['course_uuid'] \
            if 'course_uuid' in self.request.data \
            else CourseRun.objects.select_related('course').get(
                    key__iexact=self.request.data['course_id']
                ).course.uuid

        program = self.get_queryset().first()
        course = Course.objects.get(uuid=course_uuid)
        if course in program.courses.all():
            raise ValidationError(
                'Course uuid ({}) already exist in the program.'.format(course_uuid)
            )
        program.courses.add(course)

        # After adding a new course into Program, make sure to update all the Program Team Member are all in this new Course's Team.
        # PATCH: localhost:18000/api/team/v0/team_membership? course_id, program_uuid
        return Response(
            {'course_uuid': course_uuid}, status=status.HTTP_201_CREATED
        )

    def delete(self, request, *args, **kwargs):
        course_uuid = self.request.data.get('course_uuid')
        program = self.get_queryset().first()
        course = program.courses.get(uuid=course_uuid)

        program.courses.remove(course)

        return Response(
            {'course_uuid': course_uuid}, status=status.HTTP_200_OK
        )

    def patch(self, request, *args, **kwargs):
        course_uuid = self.request.data.get('course_uuid')
        program = self.get_queryset().first()
        if program.order_courses_by_start_date:
            raise ValidationError(
                'Please assign `order_courses_by_start_date=False` first'
            )
        target_order = int(request.data.get('order_no'))  # Zero based index !
        course_id_ = program.courses.get(uuid=course_uuid).id
        # Get courses ids & orders vector
        with connection.cursor() as cur:
            cur.execute(
                r"SELECT course_id, sort_value FROM course_metadata_program_courses WHERE program_id={} ORDER BY sort_value ASC".format(
                    program.id)
            )
            const_courses_orders = cur.fetchall()
        courses_ids = [c[0] for c in const_courses_orders]
        source_order = courses_ids.index(course_id_)
        # Move element to a new position
        if target_order >= len(courses_ids) or source_order == target_order:
            raise ValidationError('Target index is a invalid value.')
        courses_ids.insert(
            target_order, int(courses_ids.pop(source_order))
        )  # Sorted.
        # Dump into data table
        with transaction.atomic(), connection.cursor() as cur:
            start_index = min(source_order, target_order)
            for index, course_id in enumerate(courses_ids[start_index:], start=start_index):
                cur.execute(
                    r"UPDATE course_metadata_program_courses SET sort_value={} WHERE course_id={} and program_id={}".format(
                        const_courses_orders[index][1], course_id, program.id
                    )
                )

        return Response(
            {'course_uuid': course_uuid}, status=status.HTTP_200_OK
        )
