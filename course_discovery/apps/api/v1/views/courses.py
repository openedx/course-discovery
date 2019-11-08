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
    Course, CourseEditor, CourseEntitlement, CourseRun, CourseType, CourseUrlSlug, Organization, Program, Seat,
    SeatType, Video
)
from course_discovery.apps.course_metadata.utils import (
    create_missing_entitlement, ensure_draft_world, validate_course_number
)

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
            logger.exception(_('An error occurred while setting Course or Course Run data.'))
            return Response(_('Failed to set data: {}').format(str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
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
        }
        url_slug = request.data.get('url_slug', '')
        # DISCO-1399: Remove this variable declaration
        entitlement_type = request.data.get('mode')
        course_type = request.data.get('type')

        missing_values = [k for k, v in course_creation_fields.items() if v is None]
        # DISCO-1399: Remove this if statement
        if not entitlement_type and not course_type:
            missing_values.append('mode')
        error_message = ''
        if missing_values:
            error_message += ''.join([_('Missing value for: [{name}]. ').format(name=name) for name in missing_values])
        if not Organization.objects.filter(key=course_creation_fields['org']).exists():
            error_message += _('Organization [{org}] does not exist. ').format(org=course_creation_fields['org'])
        # DISCO-1399: This if statement isn't needed anymore
        if entitlement_type and not SeatType.objects.filter(slug=entitlement_type).exists():
            error_message += _('Entitlement Track [{entitlement_type}] does not exist. ').format(
                entitlement_type=entitlement_type
            )
        if not entitlement_type and course_type and not CourseType.objects.filter(uuid=course_type).exists():
            error_message += _('Course Type [{course_type}] does not exist. ').format(course_type=course_type)
        if error_message:
            return Response((_('Incorrect data sent. ') + error_message).strip(), status=status.HTTP_400_BAD_REQUEST)

        partner = request.site.partner
        course_creation_fields['partner'] = partner.id
        course_creation_fields['key'] = self.get_course_key(course_creation_fields)
        # DISCO-1399: Add this into the above declaration of course_creation_fields. Adding it in here for now since
        # we do not want it to be reported as a missing value since it's not required yet.
        course_creation_fields['type'] = course_type

        validate_course_number(course_creation_fields['number'])

        serializer = self.get_serializer(data=course_creation_fields)
        serializer.is_valid(raise_exception=True)

        # Confirm that this course doesn't already exist in an official non-draft form
        if Course.objects.filter(partner=partner, key=course_creation_fields['key']).exists():
            raise Exception(_('A course with key {key} already exists.').format(key=course_creation_fields['key']))

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

        # DISCO-1399: No need to check the if else. It will always be course.type
        # New flow for courses using CourseType model
        if course.type:
            entitlement_types = course.type.entitlement_types.all()
        else:
            entitlement_types = [SeatType.objects.get(slug=entitlement_type)]
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

    # DISCO-1399: This whole helper can be removed
    def update_entitlement_helper(self, course, data, partial=False):
        """ Finds and updates an existing entitlement from the incoming data, with verification. """
        if 'mode' not in data:
            raise ValidationError(_('Entitlements must have a mode specified.'))

        entitlement_type = SeatType.objects.filter(slug=data['mode']).first()
        if not entitlement_type:
            raise ValidationError(_('Entitlement mode {} not found.').format(data['mode']))

        return self.update_entitlement(course, data, entitlement_type, partial)

    # DISCO-1399: You might be able to simplify this function once you can guarantee use of course type
    def update_entitlement(self, course, data, entitlement_type, partial=False):
        """ Finds and updates an existing entitlement from the incoming data, with verification """
        entitlement = CourseEntitlement.everything.filter(course=course, draft=True).first()
        if not entitlement:
            raise ValidationError(_('Existing entitlement not found for course {0}.')
                                  .format(course.key))

        # We want to allow upgrading an entitlement from Audit -> Verified, but allow no other
        # entitlement type changes. We use the official version existing as an indicator for
        # ecom products having already been created.
        entitlement_type_switch_whitelist = {Seat.AUDIT: Seat.VERIFIED}
        if (course.official_version and entitlement.mode != entitlement_type and
                entitlement_type_switch_whitelist.get(entitlement.mode.slug) != entitlement_type.slug):
            raise ValidationError(_('Switching entitlement types after being reviewed is not supported. Please reach '
                                    'out to your project coordinator for additional help if necessary.'))

        # We have an entitlement object, now let's deserialize the incoming data and update it
        serializer = CourseEntitlementSerializer(entitlement, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    # DISCO-1399: You might be able to removew the too-many-statements disable since it should get rid
    # of a number of if statements since we don't need to check for `if data.get('type')`
    @writable_request_wrapper
    def update_course(self, data, partial=False):  # pylint: disable=too-many-statements
        """ Updates an existing course from incoming data. """
        changed = False
        # Sending draft=False means the course data is live and updates should be pushed out immediately
        draft = data.pop('draft', True)
        # Pop nested writables that we will handle ourselves (the serializer won't handle them)
        # DISCO-1399: entitlements should stop being sent so no need to pop them off
        entitlements_data = data.pop('entitlements', [])
        image_data = data.pop('image', None)
        video_data = data.pop('video', None)
        url_slug = data.pop('url_slug', '')

        # Get and validate object serializer
        course = self.get_object()
        course = ensure_draft_world(course, course_type=data.get('type'))  # always work on drafts
        serializer = self.get_serializer(course, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # First, update nested entitlements
        entitlements = []
        # New flow for courses using CourseType model
        # DISCO-1399: I think pretty much the whole 'else' can be removed.
        prices = data.get('prices', {})
        if data.get('type'):
            course_type = CourseType.objects.get(uuid=data.get('type'))
            entitlement_types = course_type.entitlement_types.all()
            for entitlement_type in entitlement_types:
                price = prices.get(entitlement_type.slug)
                if price is None:
                    continue
                data = {'mode': entitlement_type.slug, 'price': price}
                entitlements.append(self.update_entitlement(course, data, entitlement_type, partial=partial))
                changed = changed or format(float(price), '.2f') != str(course.entitlements.first().price)
        else:
            for entitlement_data in entitlements_data:
                if entitlement_data == {}:
                    continue
                entitlements.append(self.update_entitlement_helper(course, entitlement_data, partial=partial))
                # We set changed to True here if the price of the course is being updated
                changed = changed or (
                    format(float(entitlement_data['price']), '.2f') != str(course.entitlements.first().price)
                )
                prices[entitlement_data['mode']] = entitlement_data['price']
        if entitlements:
            course.entitlements.set(entitlements)
            # DISCO-1399: This whole if can be removed. Updating or creating seats
            # is being moved to the course run endpoint.
            if not course.type:
                # If entitlements were updated, we also want to update seats
                for course_run in course.active_course_runs:
                    course_run.update_or_create_seats(course_run.type, prices)

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
            image_data = ContentFile(base64.b64decode(imgstr), name='tmp.{extension}'.format(extension=ext))
            course.image.save(image_data.name, image_data)

        # If price didnt change, check the other fields on the course
        # (besides image and video, they are popped off above)
        changed = changed or reviewable_data_has_changed(course, serializer.validated_data.items())

        if url_slug:
            validators.validate_slug(url_slug)
            all_course_historical_slugs = CourseUrlSlug.objects.filter(url_slug=url_slug, partner=course.partner)
            all_course_historical_slugs_excluding_present = all_course_historical_slugs.exclude(
                course__uuid=course.uuid)
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
        return super(CourseViewSet, self).list(request, *args, **kwargs)

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

        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)
