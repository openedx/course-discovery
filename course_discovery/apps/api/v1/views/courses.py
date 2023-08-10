import base64
import logging
import re

from django.core import validators
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_framework_filters
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.permissions import IsCourseEditorOrReadOnly
from course_discovery.apps.api.serializers import CourseEntitlementSerializer, MetadataWithType
from course_discovery.apps.api.utils import get_query_param, reviewable_data_has_changed
from course_discovery.apps.api.v1.exceptions import EditableAndQUnsupported
from course_discovery.apps.api.v1.views.course_runs import CourseRunViewSet
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX, COURSE_UUID_REGEX
from course_discovery.apps.course_metadata.models import (
    Collaborator, Course, CourseEditor, CourseEntitlement, CourseRun, CourseType, CourseUrlSlug, Organization, Program,
    Seat, Video
)
from course_discovery.apps.course_metadata.utils import (
    create_missing_entitlement, ensure_draft_world, validate_course_number
)
from course_discovery.apps.publisher.utils import is_publisher_user

logger = logging.getLogger(__name__)


def writable_request_wrapper(method):
    def inner(*args, **kwargs):
        try:
            with transaction.atomic():
                return method(*args, **kwargs)
        except ValidationError as exc:
            return Response(exc.message if hasattr(exc, 'message') else str(exc),
                            status=status.HTTP_400_BAD_REQUEST)
        except (PermissionDenied, Http404):
            raise  # just pass these along
        except Exception as e:  # pylint: disable=broad-except
            content = str(e)
            if hasattr(e, 'content'):
                content = e.content.decode('utf8') if isinstance(e.content, bytes) else e.content
            msg = _('Failed to set data: {}').format(content)
            logger.exception(msg)
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
    return inner


# pylint: disable=useless-super-delegation
class CourseViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    """ Course resource. """

    filter_backends = (DjangoFilterBackend, rest_framework_filters.OrderingFilter)
    filterset_class = filters.CourseFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX + '|' + COURSE_UUID_REGEX
    permission_classes = (IsAuthenticated, IsCourseEditorOrReadOnly,)
    serializer_class = serializers.CourseWithProgramsSerializer
    metadata_class = MetadataWithType
    metadata_related_choices_whitelist = ('mode', 'level_type', 'subjects',)

    course_key_regex = re.compile(COURSE_ID_REGEX)
    course_uuid_regex = re.compile(COURSE_UUID_REGEX)

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        key = self.kwargs['key']

        if self.course_key_regex.match(key):
            filter_key = 'key'
        elif self.course_uuid_regex.match(key):
            filter_key = 'uuid'

        filter_kwargs = {filter_key: key}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def get_queryset(self):
        partner = self.request.site.partner
        q = self.request.query_params.get('q')
        # We don't want to create an additional elasticsearch index right now for draft courses, so we
        # try to implement a basic search behavior with this pubq parameter here against key and name.
        pub_q = self.request.query_params.get('pubq')
        edit_method = self.request.method not in SAFE_METHODS
        edit_mode = get_query_param(self.request, 'editable') or edit_method

        if edit_mode and q:
            raise EditableAndQUnsupported()

        if edit_mode and (not self.request.user.is_staff and not is_publisher_user(self.request.user)):
            raise PermissionDenied

        if edit_mode:
            # Start with either draft versions or real versions of the courses
            queryset = Course.objects.filter_drafts()
            queryset = CourseEditor.editable_courses(self.request.user, queryset, check_editors=edit_method)
        else:
            queryset = self.queryset

        if q:
            queryset = Course.search(q, queryset=queryset)
            queryset = self.get_serializer_class().prefetch_queryset(queryset=queryset, partner=partner)
        else:
            if edit_mode:
                course_runs = CourseRun.objects.filter_drafts(course__partner=partner)
            else:
                course_runs = CourseRun.objects.filter(course__partner=partner)

            if not get_query_param(self.request, 'include_hidden_course_runs'):
                course_runs = course_runs.exclude(hidden=True)

            if get_query_param(self.request, 'marketable_course_runs_only'):
                course_runs = course_runs.marketable().active()

            if get_query_param(self.request, 'marketable_enrollable_course_runs_with_archived'):
                course_runs = course_runs.marketable().enrollable()

            if get_query_param(self.request, 'published_course_runs_only'):
                course_runs = course_runs.filter(status=CourseRunStatus.Published)

            if get_query_param(self.request, 'include_deleted_programs'):
                programs = Program.objects.all()
            else:
                programs = Program.objects.exclude(status=ProgramStatus.Deleted)

            queryset = self.get_serializer_class().prefetch_queryset(
                queryset=queryset,
                course_runs=course_runs,
                partner=partner,
                programs=programs,
            )
        if pub_q and edit_mode:
            return queryset.filter(Q(key__icontains=pub_q) | Q(title__icontains=pub_q)).order_by(Lower('key'))

        return queryset.order_by(Lower('key'))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        query_params = ['exclude_utm', 'include_deleted_programs']

        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        return context

    def get_course_key(self, data):
        return '{org}+{number}'.format(org=data['org'], number=data['number'])

    @writable_request_wrapper
    def create(self, request, *args, **kwargs):
        """
        Create a Course, Course Entitlement, and Entitlement.
        """
        course_run_creation_fields = request.data.pop('course_run', None)
        course_creation_fields = {
            'title': request.data.get('title'),
            'number': request.data.get('number'),
            'org': request.data.get('org'),
            'type': request.data.get('type'),
        }
        url_slug = request.data.get('url_slug', '')

        missing_values = [k for k, v in course_creation_fields.items() if v is None]
        error_message = ''
        if missing_values:
            error_message += ''.join([_('Missing value for: [{name}]. ').format(name=name) for name in missing_values])
        if not Organization.objects.filter(key=course_creation_fields['org']).exists():
            error_message += _('Organization [{org}] does not exist. ').format(org=course_creation_fields['org'])
        if not CourseType.objects.filter(uuid=course_creation_fields['type']).exists():
            error_message += _('Course Type [{course_type}] does not exist. ').format(
                course_type=course_creation_fields['type'])
        if error_message:
            return Response((_('Incorrect data sent. ') + error_message).strip(), status=status.HTTP_400_BAD_REQUEST)

        partner = request.site.partner
        course_creation_fields['partner'] = partner.id
        course_creation_fields['key'] = self.get_course_key(course_creation_fields)

        validate_course_number(course_creation_fields['number'])

        serializer = self.get_serializer(data=course_creation_fields)
        serializer.is_valid(raise_exception=True)

        # Confirm that this course doesn't already exist in an official non-draft form
        if Course.objects.filter(partner=partner, key=course_creation_fields['key']).exists():
            raise Exception(_('A course with key [{key}] already exists.').format(key=course_creation_fields['key']))

        # if a manually entered url_slug, ensure it's not already taken (auto-generated are guaranteed uniqueness)
        if url_slug:
            validators.validate_slug(url_slug)
            if CourseUrlSlug.objects.filter(url_slug=url_slug, partner=partner).exists():
                raise Exception(_('Course creation was unsuccessful. The course URL slug ‘[{url_slug}]’ is already in '
                                  'use. Please update this field and try again.').format(url_slug=url_slug))

        course = serializer.save(draft=True)
        course.set_active_url_slug(url_slug)

        organization = Organization.objects.get(key=course_creation_fields['org'])
        course.authoring_organizations.add(organization)

        collaborators_uuid = request.data.get('collaborators')
        if collaborators_uuid:
            collaborators = Collaborator.objects.filter(uuid__in=collaborators_uuid)
            course.collaborators.add(*collaborators)

        entitlement_types = course.type.entitlement_types.all()
        prices = request.data.get('prices', {})
        for entitlement_type in entitlement_types:
            CourseEntitlement.objects.create(
                course=course,
                mode=entitlement_type,
                partner=partner,
                price=prices.get(entitlement_type.slug, 0),
                draft=True,
            )

        CourseEditor.objects.create(
            user=request.user,
            course=course,
        )

        # We want to create the course run here so it is captured as part of the atomic transaction.
        # Note: We have to send the request object as well because it is used for its metadata
        # (like request.user and is set as part of the serializer context)
        if course_run_creation_fields:
            course_run_creation_fields.update({'course': course.key, 'prices': prices})
            run_response = CourseRunViewSet().create_run_helper(course_run_creation_fields, request)
            if run_response.status_code != 201:
                raise Exception(str(run_response.data))

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update_entitlement(self, course, entitlement_type, price, partial=False):
        """
        Finds and updates an existing entitlement from the incoming data, with verification.

        Will create an entitlement if we're switching from Audit.
        Returns a tuple of (CourseEntitlement, bool) where the second value is whether the entitlement changed.
        """
        entitlement = CourseEntitlement.everything.filter(course=course, draft=True).first()
        existing_slug = entitlement.mode.slug if entitlement else Seat.AUDIT

        # We want to allow upgrading an entitlement from Audit -> Verified, but allow no other
        # entitlement type changes. We use the official version existing as an indicator for
        # ecom products having already been created.
        entitlement_type_switch_whitelist = {Seat.AUDIT: Seat.VERIFIED}
        if (course.official_version and existing_slug != entitlement_type.slug and
                entitlement_type_switch_whitelist.get(existing_slug) != entitlement_type.slug):
            raise ValidationError(_('Switching entitlement types after being reviewed is not supported. Please reach '
                                    'out to your project coordinator for additional help if necessary.'))

        if entitlement:
            data = {'mode': entitlement_type.slug, 'price': price}
            serializer = CourseEntitlementSerializer(entitlement, data=data, partial=partial)
            serializer.is_valid(raise_exception=True)
            return serializer.save(), entitlement.price != float(price)
        else:
            return (CourseEntitlement.objects.create(
                course=course,
                mode=entitlement_type,
                partner=course.partner,
                price=price,
                draft=True,
            ), True)

    def log_request_subjects_and_prices(self, data, course):  # pragma: no cover
        req_subjects = ', '.join(data.get('subjects', []))
        current_subjects = ', '.join(list(map(lambda s: s.slug, course.subjects.all())))
        prices = data.get('prices', {})
        logger.info(
            'UPDATE to course uuid - {uuid}, req subjects - [{req_subjects}], request prices - {prices}, '
            'current subjects - [{current_subjects}]'.format(uuid=data.get('uuid'), req_subjects=req_subjects,
                                                             prices=prices, current_subjects=current_subjects)
        )

    @writable_request_wrapper
    def update_course(self, data, partial=False):  # pylint: disable=too-many-statements
        """ Updates an existing course from incoming data. """

        # logging to help debug error around course url slugs incrementing
        logger.info('The raw course data coming from publisher is {}.'.format(data))

        changed = False
        # Sending draft=False means the course data is live and updates should be pushed out immediately
        draft = data.pop('draft', True)
        image_data = data.pop('image', None)
        video_data = data.pop('video', None)
        url_slug = data.pop('url_slug', '')

        # Get and validate object serializer
        course = self.get_object()
        course = ensure_draft_world(course)  # always work on drafts
        serializer = self.get_serializer(course, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # TEMPORARY - log incoming request (subject and prices) for all course updates, see Jira DISCO-1593
        self.log_request_subjects_and_prices(data, course)

        # First, update course entitlements
        if data.get('type') or data.get('prices'):
            entitlements = []
            prices = data.get('prices', {})
            course_type = CourseType.objects.get(uuid=data.get('type')) if data.get('type') else course.type
            entitlement_types = course_type.entitlement_types.all()
            for entitlement_type in entitlement_types:
                price = prices.get(entitlement_type.slug)
                if price is None:
                    continue
                entitlement, did_change = self.update_entitlement(course, entitlement_type, price, partial=partial)
                entitlements.append(entitlement)
                changed = changed or did_change
            # Deleting entitlements here since they would be orphaned otherwise.
            # One example of how this situation can happen is if a course team is switching between
            # "Verified and Audit" and "Audit Only" before actually publishing their course run.
            course.entitlements.exclude(mode__in=entitlement_types).delete()
            course.entitlements.set(entitlements)

        # Save video if a new video source is provided
        if (video_data and video_data.get('src') and
           (not course.video or video_data.get('src') != course.video.src)):
            video, __ = Video.objects.get_or_create(src=video_data['src'])
            course.video = video

        # Save image and convert to the correct format
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            # base64 encoded image - decode
            file_format, imgstr = image_data.split(';base64,')  # format ~= data:image/X;base64,/xxxyyyzzz/
            ext = file_format.split('/')[-1]  # guess file extension
            image_data = ContentFile(base64.b64decode(imgstr), name=f'tmp.{ext}')
            course.image.save(image_data.name, image_data)

        if data.get('collaborators'):
            collaborators_uuids = data.get('collaborators')
            collaborators = Collaborator.objects.filter(uuid__in=collaborators_uuids)
            course.collaborators.add(*collaborators)

        # If price didnt change, check the other fields on the course
        # (besides image and video, they are popped off above)
        changed = changed or reviewable_data_has_changed(course, serializer.validated_data.items())

        if url_slug:
            validators.validate_slug(url_slug)
            all_course_historical_slugs_excluding_present = CourseUrlSlug.objects.filter(
                url_slug=url_slug, partner=course.partner).exclude(course__uuid=course.uuid)
            if all_course_historical_slugs_excluding_present.exists():
                raise Exception(
                    _('Course edit was unsuccessful. The course URL slug ‘[{url_slug}]’ is already in use. '
                      'Please update this field and try again.').format(url_slug=url_slug))

        # Then the course itself
        course = serializer.save()
        if url_slug:
            course.set_active_url_slug(url_slug)

        if not draft:
            for course_run in course.active_course_runs:
                if course_run.status == CourseRunStatus.Published:
                    # This will also update the course
                    course_run.update_or_create_official_version()

        # Revert any Reviewed course runs back to Unpublished
        if changed:
            for course_run in course.course_runs.filter(status=CourseRunStatus.Reviewed):
                course_run.status = CourseRunStatus.Unpublished
                course_run.save()
                course_run.official_version.status = CourseRunStatus.Unpublished
                course_run.official_version.save()

        # hack to get the correctly-updated url slug into the response
        return_dict = {'url_slug': course.active_url_slug}
        return_dict.update(serializer.data)
        return Response(return_dict)

    def update(self, request, *_args, **_kwargs):
        """ Update details for a course. """
        return self.update_course(request.data, partial=False)

    def partial_update(self, request, *_args, **_kwargs):
        """ Partially update details for a course. """
        return self.update_course(request.data, partial=True)

    def destroy(self, _request, *_args, **_kwargs):
        """ Delete a course. """
        # Not supported
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def list(self, request, *args, **kwargs):
        """ List all courses.
         ---
        parameters:
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
            - name: keys
              description: Filter by keys (comma-separated list)
              required: false
              type: string
              paramType: query
              multiple: false
            - name: include_hidden_course_runs
              description: Include course runs that are hidden in the response.
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: marketable_course_runs_only
              description: Restrict returned course runs to those that are published, have seats,
                and are enrollable or will be enrollable in the future
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
            - name: published_course_runs_only
              description: Filter course runs by published ones only
              required: false
              type: integer
              paramType: query
              mulitple: false
            - name: q
              description: Elasticsearch querystring query. This filter takes precedence over other filters.
              required: false
              type: string
              paramType: query
              multiple: false
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for a course. """
        # Check if we can convert from run-level seat pricing to course-level entitlements.
        #
        # Yes, creating an object is kind of an odd thing to do on a GET endpoint - but it's a one time migration
        # to entitlements and subsequent calls will not make further objects.
        # This was deemed simpler than faking that an entitlement exists in the response and making the object when
        # a client calls PATCH.
        course = self.get_object()
        if get_query_param(request, 'editable') and not course.entitlements.exists():
            create_missing_entitlement(course)

        return super().retrieve(request, *args, **kwargs)
