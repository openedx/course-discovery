import logging

from django.db import transaction
from django.db.models.functions import Lower
from django.http.response import Http404
from django.utils.translation import ugettext as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.permissions import IsCourseRunEditorOrDjangoOrReadOnly
from course_discovery.apps.api.serializers import MetadataWithRelatedChoices
from course_discovery.apps.api.utils import StudioAPI, get_query_param, reviewable_data_has_changed
from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.constants import COURSE_RUN_ID_REGEX
from course_discovery.apps.course_metadata.models import Course, CourseEditor, CourseRun
from course_discovery.apps.course_metadata.utils import ensure_draft_world
from course_discovery.apps.publisher.utils import is_publisher_user

log = logging.getLogger(__name__)


def writable_request_wrapper(method):
    def inner(*args, **kwargs):
        try:
            with transaction.atomic():
                return method(*args, **kwargs)
        except (PermissionDenied, ValidationError, Http404):
            raise  # just pass these along
        except Exception as e:  # pylint: disable=broad-except
            content = str(e)
            if hasattr(e, 'content'):
                content = e.content.decode('utf8') if isinstance(e.content, bytes) else e.content
            msg = _('Failed to set course run data: {}').format(content)
            log.exception(msg)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
    return inner


# pylint: disable=useless-super-delegation
class CourseRunViewSet(viewsets.ModelViewSet):
    """ CourseRun resource. """
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = filters.CourseRunFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_RUN_ID_REGEX
    ordering_fields = ('start',)
    permission_classes = (IsAuthenticated, IsCourseRunEditorOrDjangoOrReadOnly)
    queryset = CourseRun.objects.all().order_by(Lower('key'))
    serializer_class = serializers.CourseRunWithProgramsSerializer
    metadata_class = MetadataWithRelatedChoices
    metadata_related_choices_whitelist = (
        'content_language', 'level_type', 'transcript_languages', 'expected_program_type', 'type'
    )

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

        if edit_mode and (not self.request.user.is_staff and not is_publisher_user(self.request.user)):
            raise PermissionDenied

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

    def get_serializer_context(self):
        context = super().get_serializer_context()
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
        return super().list(request, *args, **kwargs)  # pylint: disable=no-member

    @classmethod
    def push_to_studio(cls, request, course_run, create=False, old_course_run_key=None):
        if course_run.course.partner.studio_url:
            api = StudioAPI(course_run.course.partner.studio_api_client)
            api.push_to_studio(course_run, create, old_course_run_key, user=request.user)
        else:
            log.info('Not pushing course run info for %s to Studio as partner %s has no studio_url set.',
                     course_run.key, course_run.course.partner.short_code)

    @classmethod
    def update_course_run_image_in_studio(cls, course_run):
        if course_run.course.partner.studio_url:
            api = StudioAPI(course_run.course.partner.studio_api_client)
            api.update_course_run_image_in_studio(course_run)
        else:
            log.info('Not updating course run image for %s to Studio as partner %s has no studio_url set.',
                     course_run.key, course_run.course.partner.short_code)

    @writable_request_wrapper
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

        prices = run_data.pop('prices', {})

        # Grab any existing course run for this course (we'll use it when talking to studio to form basis of rerun)
        course_key = run_data.get('course', None)  # required field
        if not course_key:
            raise ValidationError({'course': ['This field is required.']})

        # Before creating the serializer we need to ensure the course has draft rows as expected
        # The serializer will attempt to retrieve the draft version of the Course
        course = Course.objects.filter_drafts().get(key=course_key)
        course = ensure_draft_world(course)
        old_course_run_key = run_data.pop('rerun', None)

        serializer = self.get_serializer(data=run_data)
        serializer.is_valid(raise_exception=True)

        # Save run to database
        course_run = serializer.save(draft=True)

        course_run.update_or_create_seats(course_run.type, prices)

        # Set canonical course run if needed (done this way to match historical behavior - but shouldn't this be
        # updated *each* time we make a new run?)
        if not course.canonical_course_run:
            course.canonical_course_run = course_run
            course.save()
        elif not old_course_run_key:
            # On a rerun, only set the old course run key to the canonical key if a rerun hasn't been provided
            # This will prevent a breaking change if users of this endpoint don't choose to provide a key on rerun
            old_course_run_key = course.canonical_course_run.key

        if old_course_run_key:
            old_course_run = CourseRun.objects.filter_drafts().get(key=old_course_run_key)
            course_run.language = old_course_run.language
            course_run.min_effort = old_course_run.min_effort
            course_run.max_effort = old_course_run.max_effort
            course_run.weeks_to_complete = old_course_run.weeks_to_complete
            course_run.save()
            course_run.staff.set(old_course_run.staff.all())
            course_run.transcript_languages.set(old_course_run.transcript_languages.all())

        # And finally, push run to studio
        self.push_to_studio(self.request, course_run, create=True, old_course_run_key=old_course_run_key)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def create(self, request, *args, **kwargs):
        """ Create a course run object. """
        response = self.create_run_helper(request.data)
        if response.status_code == 201:
            run_key = response.data.get('key')
            course_run = CourseRun.everything.get(key=run_key, draft=True)
            self.update_course_run_image_in_studio(course_run)

        return response

    @writable_request_wrapper
    def _update_course_run(self, course_run, draft, changed, serializer, request, prices):
        save_kwargs = {}
        # If changes are made after review and before publish, revert status to unpublished.
        # Unless we're just switching the status
        non_exempt_update = changed and course_run.status == CourseRunStatus.Reviewed
        if non_exempt_update:
            save_kwargs['status'] = CourseRunStatus.Unpublished
            official_run = course_run.official_version
            official_run.status = CourseRunStatus.Unpublished
            official_run.save()
        # When the course run is being updated and is coming from the Unpublished state, we always want to set
        # it's status to in legal review.  If it is coming from the Reviewed state, we only want to put it
        # back into legal review if a non exempt field was changed (expected_program_name and expected_program_type)
        if not draft and (course_run.status == CourseRunStatus.Unpublished or non_exempt_update):
            save_kwargs['status'] = CourseRunStatus.LegalReview

        course_run = serializer.save(**save_kwargs)

        if course_run in course_run.course.active_course_runs:
            course_run.update_or_create_seats(course_run.type, prices)

        self.push_to_studio(request, course_run, create=False)

        # Published course runs can be re-published directly or course runs that remain in the Reviewed
        # state can update their official version. We want to do this even in the Reviewed case for
        # when an exempt field is changed and we still want to update the official even though we don't
        # want to completely unpublish it.
        if ((not draft and course_run.status == CourseRunStatus.Published) or
           course_run.status == CourseRunStatus.Reviewed):
            course_run.update_or_create_official_version()

        return Response(serializer.data)

    def handle_internal_review(self, request, serializer):
        # Disallow updates on non internal review fields while course is in review
        for key in request.data.keys():
            if key not in CourseRun.INTERNAL_REVIEW_FIELDS:
                return Response(
                    _('Can only update status, ofac restrictions, and ofac comment'),
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer.save()
        return Response(serializer.data)

    def update(self, request, **kwargs):
        # logging to help debug error around course url slugs incrementing
        log.info('The raw course run data coming from publisher is {}.'.format(request.data))

        # Update one, or more, fields for a course run.
        course_run = self.get_object()
        course_run = ensure_draft_world(course_run)  # always work on drafts
        partial = kwargs.pop('partial', False)
        # Sending draft=False triggers the review process for unpublished courses
        draft = request.data.pop('draft', True)  # Don't let draft parameter trickle down
        prices = request.data.pop('prices', {})

        serializer = self.get_serializer(course_run, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Handle staff update on course run in review with valid status transition
        if (request.user.is_staff and course_run.in_review and 'status' in request.data and
                request.data['status'] in CourseRunStatus.INTERNAL_STATUS_TRANSITIONS):
            return self.handle_internal_review(request, serializer)

        # Handle regular non-internal update
        request.data.pop('status', None)  # Status management is handled in the model
        serializer.validated_data.pop('status', None)  # Status management is handled in the model
        # Disallow patch or put if the course run is in review.
        if course_run.in_review:
            return Response(
                _('Course run is in review. Editing disabled.'),
                status=status.HTTP_403_FORBIDDEN
            )
        # Disallow internal review fields when course run is not in review
        for key in request.data.keys():
            if key in CourseRun.INTERNAL_REVIEW_FIELDS:
                return Response(
                    _('Invalid parameter'),
                    status=status.HTTP_400_BAD_REQUEST
                )

        changed = reviewable_data_has_changed(
            course_run, serializer.validated_data.items(), CourseRun.STATUS_CHANGE_EXEMPT_FIELDS)
        response = self._update_course_run(course_run, draft, changed, serializer, request, prices)

        self.update_course_run_image_in_studio(course_run)

        return response

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course run. """
        return super().retrieve(request, *args, **kwargs)  # pylint: disable=no-member

    @action(detail=False)
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
