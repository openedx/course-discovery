import logging

from django.db import transaction
from django.db.models.fields.related import ManyToManyField
from django.db.models.functions import Lower
from django.http.response import Http404
from django.utils.translation import ugettext as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import list_route
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from sortedm2m.fields import SortedManyToManyField

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.permissions import IsCourseRunEditorOrDjangoOrReadOnly
from course_discovery.apps.api.serializers import MetadataWithRelatedChoices
from course_discovery.apps.api.utils import StudioAPI, get_query_param
from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.constants import COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import Course, CourseEditor, CourseRun
from course_discovery.apps.course_metadata.utils import ensure_draft_world


log = logging.getLogger(__name__)


def writable_request_wrapper(method):
    def inner(*args, **kwargs):
        try:
            with transaction.atomic():
                return method(*args, **kwargs)
        except (PermissionDenied, ValidationError, Http404):
            raise  # just pass these along
        except Exception as e:  # pylint: disable=broad-except
            log.exception(_('An error occurred while setting course run data.'))
            return Response(_('Failed to set course run data: {}').format(str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
    return inner


# pylint: disable=no-member
class CourseRunViewSet(viewsets.ModelViewSet):
    """ CourseRun resource. """
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filter_class = filters.CourseRunFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_RUN_ID_REGEX
    ordering_fields = ('start',)
    permission_classes = (IsAuthenticated, IsCourseRunEditorOrDjangoOrReadOnly)
    queryset = CourseRun.objects.all().order_by(Lower('key'))
    serializer_class = serializers.CourseRunWithProgramsSerializer
    metadata_class = MetadataWithRelatedChoices
    metadata_related_choices_whitelist = ('content_language', 'level_type', 'transcript_languages',)

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        """ List one course run
        ---
        parameters:
            - name: include_deleted_programs
              description: Will include deleted programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        q = self.request.query_params.get('q')
        partner = self.request.site.partner
        edit_mode = get_query_param(self.request, 'editable') or self.request.method not in SAFE_METHODS

        if edit_mode and q:
            raise EditableAndQUnsupported()

        if edit_mode:
            queryset = CourseRun.objects.filter_drafts()
            queryset = CourseEditor.editable_course_runs(self.request.user, queryset)
        else:
            queryset = self.queryset

        if q:
            qs = SearchQuerySetWrapper(CourseRun.search(q).filter(partner=partner.short_code))
            # This is necessary to avoid issues with the filter backend.
            qs.model = self.queryset.model
            return qs

        queryset = queryset.filter(course__partner=partner)
        return self.get_serializer_class().prefetch_queryset(queryset=queryset)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({
            'exclude_utm': get_query_param(self.request, 'exclude_utm'),
            'include_deleted_programs': get_query_param(self.request, 'include_deleted_programs'),
            'include_unpublished_programs': get_query_param(self.request, 'include_unpublished_programs'),
            'include_retired_programs': get_query_param(self.request, 'include_retired_programs'),
        })

        return context

    def list(self, request, *args, **kwargs):
        """ List all course runs.
        ---
        parameters:
            - name: q
              description: Elasticsearch querystring query. This filter takes precedence over other filters.
              required: false
              type: string
              paramType: query
              multiple: false
            - name: keys
              description: Filter by keys (comma-separated list)
              required: false
              type: string
              paramType: query
              multiple: false
            - name: hidden
              description: Filter based on wether the course run is hidden from search.
              required: false
              type: Boolean
              paramType: query
              multiple: false
            - name: active
              description: Retrieve active course runs. A course is considered active if its end date has not passed,
                and it is open for enrollment.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: marketable
              description: Retrieve marketable course runs. A course run is considered marketable if it has a
                marketing slug.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: exclude_utm
              description: Exclude UTM parameters from marketing URLs.
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: include_deleted_programs
              description: Will include deleted programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: include_unpublished_programs
              description: Will include unpublished programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
            - name: include_retired_programs
              description: Will include retired programs in the associated programs array
              required: false
              type: integer
              paramType: query
              multiple: false
        """
        return super(CourseRunViewSet, self).list(request, *args, **kwargs)

    @classmethod
    def push_to_studio(cls, request, course_run, create=False, old_course_run=None):
        if course_run.course.partner.studio_url:
            api = StudioAPI(course_run.course.partner.studio_api_client)
            api.push_to_studio(course_run, create, old_course_run, user=request.user)
        else:
            log.info('Not pushing course run info for %s to Studio as partner %s has no studio_url set.',
                     course_run.key, course_run.course.partner.short_code)

    def create_run_helper(self, run_data, request=None):
        # These are both required to be part of self because when we call self.get_serializer, it tries
        # to set these two variables as part of the serializer context. When the endpoint is hit directly,
        # self.request should exist, but when this function is called from the Course POST endpoint in courses.py
        # we have to manually set these values.
        if not hasattr(self, 'request'):
            self.request = request  # pylint: disable=attribute-defined-outside-init
        if not hasattr(self, 'format_kwarg'):
            self.format_kwarg = None  # pylint: disable=attribute-defined-outside-init

        # Set a pacing default when creating (studio requires this to be set, even though discovery does not)
        run_data.setdefault('pacing_type', 'instructor_paced')

        # Guard against externally setting the draft state
        run_data.pop('draft', None)

        serializer = self.get_serializer(data=run_data)
        serializer.is_valid(raise_exception=True)

        # Grab any existing course run for this course (we'll use it when talking to studio to form basis of rerun)
        course_key = run_data['course']  # required field
        course = Course.objects.filter_drafts().get(key=course_key)
        course = ensure_draft_world(course)
        old_course_run = course.canonical_course_run

        # Save run to database
        course_run = serializer.save(draft=True)

        course_run.update_or_create_seats()

        # Set canonical course run if needed (done this way to match historical behavior - but shouldn't this be
        # updated *each* time we make a new run?)
        if not old_course_run:
            course.canonical_course_run = course_run
            course.save()

        # And finally, push run to studio
        self.push_to_studio(self.request, course_run, create=True, old_course_run=old_course_run)

        return serializer.data

    @writable_request_wrapper
    def create(self, request, *args, **kwargs):
        """ Create a course run object. """
        serializer_data = self.create_run_helper(request.data)

        headers = self.get_success_headers(serializer_data)
        return Response(serializer_data, status=status.HTTP_201_CREATED, headers=headers)

    @writable_request_wrapper
    def update(self, request, **kwargs):
        """ Update one, or more, fields for a course run. """
        course_run = self.get_object()
        course_run = ensure_draft_world(course_run)  # always work on drafts

        # Sending draft=False triggers the review process for unpublished courses
        draft = request.data.pop('draft', True)  # Don't let draft parameter trickle down

        # Disallow patch or put if the course run is in review.
        if course_run.in_review:
            return Response(
                _('Course run is in review. Editing disabled.'),
                status=status.HTTP_403_FORBIDDEN
            )
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(course_run, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        save_kwargs = {}
        changed = False
        for key, new_value in serializer.validated_data.items():
            original_value = getattr(course_run, key, None)
            if isinstance(new_value, list):
                field_class = CourseRun._meta.get_field(key).__class__
                original_value_elements = original_value.all()
                if len(new_value) != original_value_elements.count():
                    changed = True
                # Just use set compare since none of our fields require duplicates
                elif field_class == ManyToManyField and set(new_value) != set(original_value_elements):
                    changed = True
                elif field_class == SortedManyToManyField:
                    for new_value_element, original_value_element in zip(new_value, original_value_elements):
                        if new_value_element != original_value_element:
                            changed = True
            elif new_value != original_value:
                changed = True

        # If changes are made after review and before publish, revert status to unpublished.
        # Unless we're just switching the status
        if changed and course_run.status == CourseRunStatus.Reviewed:
            save_kwargs['status'] = CourseRunStatus.Unpublished
            # An official version should already exist, but just make sure
            official_run = course_run.update_or_create_official_version()
            official_run.status = CourseRunStatus.Unpublished
            official_run.save()

        if not draft and course_run.status != CourseRunStatus.Published:
            save_kwargs['status'] = CourseRunStatus.LegalReview

        course_run = serializer.save(**save_kwargs)

        self.push_to_studio(request, course_run, create=False)

        # Published course runs can be re-published directly
        if not draft and course_run.status == CourseRunStatus.Published:
            course_run.update_or_create_official_version()

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course run. """
        return super(CourseRunViewSet, self).retrieve(request, *args, **kwargs)

    @list_route()
    def contains(self, request):
        """
        Determine if course runs are found in the query results.

        A dictionary mapping course run keys to booleans,
        indicating course run presence, will be returned.
        ---
        serializer: serializers.ContainedCourseRunsSerializer
        parameters:
            - name: query
              description: Elasticsearch querystring query
              required: true
              type: string
              paramType: query
              multiple: false
            - name: course_run_ids
              description: Comma-separated list of course run IDs
              required: true
              type: string
              paramType: query
              multiple: true
            - name: partner
              description: Filter by partner
              required: false
              type: string
              paramType: query
              multiple: false
        """
        query = request.GET.get('query')
        course_run_ids = request.GET.get('course_run_ids')
        partner = self.request.site.partner

        if query and course_run_ids:
            course_run_ids = course_run_ids.split(',')
            course_runs = CourseRun.search(query).filter(partner=partner.short_code).filter(key__in=course_run_ids). \
                values_list('key', flat=True)
            contains = {course_run_id: course_run_id in course_runs for course_run_id in course_run_ids}

            instance = {'course_runs': contains}
            serializer = serializers.ContainedCourseRunsSerializer(instance)
            return Response(serializer.data)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, _request, *_args, **_kwargs):
        """ Delete a course run. """
        # Not supported
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
