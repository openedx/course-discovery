from collections import OrderedDict
from datetime import datetime

from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError
from django.db.models import Case
from django.db.models import When
from django.db import connection
from django.db import transaction
from django.http.request import QueryDict
from django.utils.translation import ugettext as _
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun
from course_discovery.apps.course_metadata.models import Program, ProgramType


class ProgramViewSet(viewsets.ModelViewSet):
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
        input_data = OrderedDict(self.request.data)

        filters = {
            'orgs': input_data['orgs']
        }
        program_uuid = self.kwargs.get(self.lookup_field)
        if program_uuid:
            filters['uuid'] = program_uuid

        return serializer_class.prefetch_queryset(
            **filters
        )

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)

        query_params = [
            'exclude_utm', 'use_full_course_serializer', 'published_course_runs_only',
            'marketable_enrollable_course_runs_with_archived'
        ]
        context['current_site_id'] = self.request.site.id

        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        # Arguments: for Draft program courses list.
        if 'courses' in self.request.data:
            # The courses list for this program.
            # We need fetch & return these courses instead of the related courses of program
            # Because these courses may belong to Draft Program Courses list.
            # Format: ['d591f0a5-92d4-47ba-8f21-bf938e559885', 'cf5fe179-8395-4a30-85ed-a4ebfa00b715']
            context['draft_program_courses_uuids'] = self.request.data['courses']

        return context

    def create(self, request, *args, **kwargs):
        input_data = OrderedDict(request.data)

        if r'type' in input_data:
            input_data[r'type'] = ProgramType.objects.get(
                name=input_data[r'type']
            )

        site_orgs = input_data.get('orgs', None)
        if not site_orgs:
            raise ValidationError('miss argument `orgs`')

        if 'status' not in input_data:
            input_data['status'] = ProgramStatus.Unpublished

        program_writer = self.get_serializer_class()  # ProgramSerializer
        writer = program_writer(
            data=input_data,
            context={'current_site_id': self.request.site.id}
        )
        if not writer.is_valid():
            if 'title' in writer.errors:
                return Response(
                    {'api_error_message': _("Path name already exist.")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            else:
                raise ValidationError(
                    'invalid arguments: {} \n fields error: {}'.format(
                        kwargs, writer.errors
                    )
                )
        else:
            # Save
            program_uuid = writer.save().uuid

            return Response(
                {'program_uuid': program_uuid},
                status=status.HTTP_201_CREATED
            )

    def update(self, request, *args, **kwargs):
        input_data = OrderedDict(request.data)

        if r'type' in input_data:
            input_data[r'type'] = ProgramType.objects.get(
                name=input_data[r'type']
            )

        if r'released_date' in input_data:
            input_data[r'released_date'] = datetime.now()

        program = self.get_object()

        # Save Draft program courses list into Mysql.
        draft_program_courses = input_data.pop('draft_program_courses', None)
        if draft_program_courses is not None:
            with transaction.atomic():
                preserved = Case(
                    *[When(uuid=pk, then=pos)
                      for pos, pk in enumerate(draft_program_courses)]
                )
                courses = Course.objects.filter(
                    uuid__in=[
                        course for course in draft_program_courses
                    ]  # UUIDs list of `Draft` Program in MongoDB.
                ).order_by(preserved)
                for c in program.courses.all():
                    program.courses.remove(c)
                for course in courses:
                    program.courses.add(course)

        writer = self.get_serializer(program, data=input_data, partial=True)
        if not writer.is_valid():
            if 'title' in writer.errors:
                return Response(
                    {'api_error_message': _("Learning path title already exist.")},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            else:
                raise ValidationError(
                    'invalid arguments: {} \n fields error: {}'.format(
                        kwargs, writer.errors
                    )
                )
        else:
            # Rename saved image if new image file name were passed.
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
            queryset = self.filter_queryset(
                Program.objects.filter(
                    orgs__in=SiteOrganization.enumerate_orgs_by_site(self.request.site.id)
                )
            )
            uuids = queryset.values_list('uuid', flat=True)

            return Response(uuids)

        return super(ProgramViewSet, self).list(request, *args, **kwargs)


class ProgramCoursesViewSet(viewsets.ModelViewSet):
    lookup_field = 'uuid'
    permission_classes = (IsAuthenticated,)
    pagination_class = ProxiedPagination

    def get_serializer_class(self):
        return serializers.MinimalProgramSerializer

    def get_queryset(self):
        filters = {
            'orgs': SiteOrganization.enumerate_orgs_by_site(
                self.request.site.id
            ),
            'program_uuid': self.kwargs['program_uuid']
        }

        return self.get_serializer_class().prefetch_queryset(**filters)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)

        # Arguments: for Draft program courses list.
        if 'courses' in self.request.data:
            # The courses list for this program.
            # We need fetch & return these courses instead of the related courses of program
            # Because these courses may belong to Draft Program Courses list.
            # Format: ['d591f0a5-92d4-47ba-8f21-bf938e559885', 'cf5fe179-8395-4a30-85ed-a4ebfa00b715']
            context['draft_program_courses_uuids'] = self.request.data['courses']

        if 'title' in self.request.data:
            context['query_by_title'] = self.request.data['title']

        return context

    def list(self, request, program_uuid):
        """Return all courses of a program
            Because we also dont paginate courses list for a Program instance
        """
        program = self.get_queryset().first()

        serializer = self.get_serializer(
            program, many=False, context={'request': self.request}
        )

        if 'courses' not in serializer.data:
            return Response(
                [], status=status.HTTP_200_OK
            )
        else:
            return Response(
                serializer.data['courses'], status=status.HTTP_200_OK
            )

    def create(self, request, *args, **kwargs):
        """Checking course for program courses list. But we don't add any courses into a program courses list.
            The inserting logic is in publish method.
        """
        if not self.request.data['course_ids']:
            raise ValidationError('Argument: `course_ids` is empty.')

        exec_flag = self.request.data.get('exec')
        post_courses_ids = self.request.data['course_ids']

        # Make sure the queryset own the same order with args: `course_ids`
        preserved = Case(
            *[When(key=pk, then=pos)
              for pos, pk in enumerate(post_courses_ids)]
        )
        course_uuids = [
            course_run.course.uuid
            for course_run in CourseRun.objects.select_related('course').filter(
                key__in=post_courses_ids
            ).order_by(preserved)
        ]

        program = self.get_queryset().first()

        if '1' == exec_flag:
            with transaction.atomic():
                for course in Course.objects.filter(uuid__in=course_uuids):
                    if course in program.courses.all():
                        continue
                    program.courses.add(course)

        if isinstance(self.request.data, QueryDict):
            self.request.data._mutable = True
        self.request.data['courses'] = course_uuids

        serializer = self.get_serializer(
            program,
            many=False
        )

        resp_courses = serializer.data['courses']

        for resp_course in resp_courses:
            # Cal. program's start/end date
            min_start = max_end = None
            for course_run in program.course_runs:
                if not min_start and course_run.start:
                    min_start = course_run.start
                elif course_run.start and course_run.start < min_start:
                    min_start = course_run.start

                if not max_end and course_run.end:
                    max_end = course_run.end
                elif course_run.end and course_run.end > max_end:
                    max_end = course_run.end
            # We need it for rendering the date range on page
            resp_course['program_start'] = min_start
            resp_course['program_end'] = max_end

        return Response(
            resp_courses,
            status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        """Remove a course from Program courses list
        """
        course_uuid = kwargs['uuid']
        program = self.get_queryset().first()
        course = program.courses.get(uuid=course_uuid)

        program.courses.remove(course)

        return Response(
            {'course_uuid': course_uuid}, status=status.HTTP_200_OK
        )

    def patch(self, request, *args, **kwargs):
        """Reorder sequence of course in Program courses list
        """
        course_uuid = self.request.data['course_uuid']
        target_order = int(request.data['order_no'])    # Zero based index !
        program = self.get_queryset().first()
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
