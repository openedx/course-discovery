import logging

from django.db import transaction
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

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.permissions import IsCourseRunEditorOrDjangoOrReadOnly
from course_discovery.apps.api.serializers import MetadataWithRelatedChoices
from course_discovery.apps.api.utils import StudioAPI, get_query_param
from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.constants import COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import Course, CourseEditor, CourseRun
from course_discovery.apps.course_metadata.utils import ensure_draft_world, set_official_state


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
            queryset = CourseRun.search(q, queryset=queryset)

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

    @writable_request_wrapper
    def create(self, request, *args, **kwargs):
        """ Create a course run object. """
        # Set a pacing default when creating (studio requires this to be set, even though discovery does not)
        request.data.setdefault('pacing_type', 'instructor_paced')

        # Guard against externally setting the draft state
        request.data.pop('draft', None)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Grab any existing course run for this course (we'll use it when talking to studio to form basis of rerun)
        course_key = request.data['course']  # required field
        course = Course.objects.filter_drafts().get(key=course_key)
        course = ensure_draft_world(course)
        old_course_run = course.canonical_course_run

        # And finally, save to database and push to studio
        course_run = serializer.save()
        course_run.draft = True
        course_run.save()
        self.push_to_studio(request, course_run, create=True, old_course_run=old_course_run)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @writable_request_wrapper
    def update(self, request, *args, **kwargs):
        """ Update one, or more, fields for a course run. """
        course_run = self.get_object()
        course_run = ensure_draft_world(course_run)  # always work on drafts

        # Disallow patch or put if the course run is in review.
        if course_run.in_review:
            return Response(
                _('Course run is in review. Editing disabled.'),
                status=status.HTTP_403_FORBIDDEN
            )

        # If changes are made after review and before publish,
        # revert status to unpublished.
        if course_run.status == CourseRunStatus.Reviewed:
            request.data['status'] = CourseRunStatus.Unpublished

        # Sending draft=False triggers the review process for unpublished courses
        draft = request.data.pop('draft', True)  # Don't let draft parameter trickle down
        if not draft and course_run.status != CourseRunStatus.Published:
            request.data['status'] = CourseRunStatus.LegalReview

        response = super().update(request, *args, **kwargs)
        self.push_to_studio(request, course_run, create=False)

        # Published courses can be re-published directly
        if not draft and course_run.status == CourseRunStatus.Published:
            set_official_state(course_run, CourseRun)

        return response

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
            course_runs = CourseRun.search(query).filter(course__partner=partner).filter(key__in=course_run_ids). \
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
