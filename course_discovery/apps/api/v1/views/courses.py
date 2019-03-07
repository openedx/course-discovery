import base64
import logging
import re

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_api_client.client import OAuthAPIClient
from rest_framework import filters as rest_framework_filters
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.api.permissions import IsCourseEditorOrReadOnly
from course_discovery.apps.api.serializers import CourseEntitlementSerializer, MetadataWithRelatedChoices
from course_discovery.apps.api.utils import get_query_param
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.constants import COURSE_ID_REGEX, COURSE_UUID_REGEX
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRun, Organization, Seat, SeatType, Video
)

logger = logging.getLogger(__name__)


class EcommerceAPIClientException(Exception):
    pass


def writable_request_wrapper(method):
    def inner(*args, **kwargs):
        try:
            with transaction.atomic():
                return method(*args, **kwargs)
        except ValidationError as exc:
            return Response(exc.message if hasattr(exc, 'message') else str(exc),
                            status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied:
            raise  # just pass a 403 along
        except EcommerceAPIClientException as e:
            logger.exception(
                _('The following error occurred while setting the Course Entitlement data in E-commerce: '
                  '{ecom_error}').format(ecom_error=e)
            )
            return Response(_('Failed to set course data due to a failure updating the product.'),
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(_('An error occurred while setting Course data.'))
            return Response(_('Failed to set course data: {}').format(str(e)),
                            status=status.HTTP_400_BAD_REQUEST)
    return inner


# pylint: disable=no-member
class CourseViewSet(viewsets.ModelViewSet):
    """ Course resource. """

    filter_backends = (DjangoFilterBackend, rest_framework_filters.OrderingFilter)
    filter_class = filters.CourseFilter
    lookup_field = 'key'
    lookup_value_regex = COURSE_ID_REGEX + '|' + COURSE_UUID_REGEX
    permission_classes = (IsAuthenticated, IsCourseEditorOrReadOnly,)
    serializer_class = serializers.CourseWithProgramsSerializer
    metadata_class = MetadataWithRelatedChoices
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

        if q:
            queryset = Course.search(q)
            queryset = self.get_serializer_class().prefetch_queryset(queryset=queryset, partner=partner)
        else:
            if get_query_param(self.request, 'include_hidden_course_runs'):
                course_runs = CourseRun.objects.filter(course__partner=partner)
            else:
                course_runs = CourseRun.objects.filter(course__partner=partner).exclude(hidden=True)

            if get_query_param(self.request, 'marketable_course_runs_only'):
                course_runs = course_runs.marketable().active()

            if get_query_param(self.request, 'marketable_enrollable_course_runs_with_archived'):
                course_runs = course_runs.marketable().enrollable()

            if get_query_param(self.request, 'published_course_runs_only'):
                course_runs = course_runs.filter(status=CourseRunStatus.Published)

            queryset = self.get_serializer_class().prefetch_queryset(
                queryset=self.queryset,
                course_runs=course_runs,
                partner=partner
            )

        return queryset.order_by(Lower('key'))

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        query_params = ['exclude_utm', 'include_deleted_programs']

        for query_param in query_params:
            context[query_param] = get_query_param(self.request, query_param)

        return context

    def get_course_key(self, data):
        return '{org}+{number}'.format(org=data['org'], number=data['number'])

    def push_ecommerce_entitlement(self, partner, course, entitlement, partial=False):
        """ Creates or updates the stockrecord information on the ecommerce side. """
        api_client = OAuthAPIClient(partner.lms_url, partner.oidc_key, partner.oidc_secret)

        if partial:
            method = 'PUT'
            url = '{0}stockrecords/{1}/'.format(partner.ecommerce_api_url, entitlement.sku)
            data = {
                'price_excl_tax': entitlement.price,
            }
        else:
            method = 'POST'
            url = '{0}products/'.format(partner.ecommerce_api_url)
            data = {
                'product_class': 'Course Entitlement',
                'title': course.title,
                'price': entitlement.price,
                'certificate_type': entitlement.mode.slug,
                'uuid': str(course.uuid),
            }

        response = api_client.request(method, url, data=data)
        if not response.ok:
            raise EcommerceAPIClientException(response.text)
        return response

    @writable_request_wrapper
    def create(self, request, *args, **kwargs):
        """
        Create a Course, Course Entitlement, and Entitlement Product in E-commerce.
        """
        course_creation_fields = {
            'title': request.data.get('title'),
            'number': request.data.get('number'),
            'org': request.data.get('org'),
            'mode': request.data.get('mode'),
        }
        missing_values = [k for k, v in course_creation_fields.items() if v is None]
        error_message = ''
        if missing_values:
            error_message += ''.join([_('Missing value for: [{name}]. ').format(name=name) for name in missing_values])
        if not Organization.objects.filter(key=course_creation_fields['org']).exists():
            error_message += _('Organization does not exist. ')
        if not SeatType.objects.filter(slug=course_creation_fields['mode']).exists():
            error_message += _('Entitlement Track does not exist. ')
        if error_message:
            return Response((_('Incorrect data sent. ') + error_message).strip(), status=status.HTTP_400_BAD_REQUEST)

        partner = request.site.partner
        course_creation_fields['partner'] = partner.id
        course_creation_fields['key'] = self.get_course_key(course_creation_fields)
        serializer = self.get_serializer(data=course_creation_fields)
        serializer.is_valid(raise_exception=True)

        course = serializer.save()

        organization = Organization.objects.get(key=course_creation_fields['org'])
        course.authoring_organizations.add(organization)

        if course_creation_fields['mode'] in Seat.ENTITLEMENT_MODES:
            price = request.data.get('price', 0.00)
            mode = SeatType.objects.get(slug=course_creation_fields['mode'])
            entitlement = CourseEntitlement.objects.create(
                course=course,
                mode=mode,
                partner=partner,
                price=price,
            )

            ecom_response = self.push_ecommerce_entitlement(partner, course, entitlement)
            stockrecord = ecom_response.json()['stockrecords'][0]
            entitlement.sku = stockrecord['partner_sku']
            entitlement.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update_entitlement(self, course, data, partial=False):
        """ Finds and updates an existing entitlement from the incoming data, with verification. """
        if 'mode' not in data:
            raise ValidationError(_('Entitlements must have a mode specified.'))

        mode = SeatType.objects.filter(slug=data['mode']).first()
        if not mode:
            raise ValidationError(_('Entitlement mode {} not found.').format(data['mode']))

        entitlement = CourseEntitlement.objects.filter(course=course, mode=mode).first()
        if not entitlement:
            raise ValidationError(_('Existing entitlement not found for mode {0} in course {1}.')
                                  .format(data['mode'], course.key))
        if not entitlement.sku:
            raise ValidationError(_('Entitlement does not have a valid SKU assigned.'))

        # We have an entitlement object, now let's deserialize the incoming data and update it
        serializer = CourseEntitlementSerializer(entitlement, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return entitlement

    @writable_request_wrapper
    def update_course(self, data, partial=False):
        """ Updates an existing course from incoming data. """
        # Pop nested writables that we will handle ourselves (the serializer won't handle them)
        entitlements_data = data.pop('entitlements', [])
        image_data = data.pop('image', None)
        video_data = data.pop('video', None)

        # Get and validate object serializer
        course = self.get_object()
        serializer = self.get_serializer(course, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # First, update nested entitlements
        entitlements = []
        for entitlement_data in entitlements_data:
            entitlements.append(self.update_entitlement(course, entitlement_data, partial=partial))

        # Save video if a new video source is provided
        if video_data and video_data['src'] and video_data['src'] != course.video.src:
            video, __ = Video.objects.get_or_create(src=video_data['src'])
            course.video = video

        # Save image and convert to the correct format
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            # base64 encoded image - decode
            file_format, imgstr = image_data.split(';base64,')  # format ~= data:image/X;base64,/xxxyyyzzz/
            ext = file_format.split('/')[-1]  # guess file extension
            image_data = ContentFile(base64.b64decode(imgstr), name='tmp.' + ext)
            course.image.save('', image_data)

        # Then the course itself
        serializer.save()

        # And finally, send updates to ecommerce
        for entitlement in entitlements:
            self.push_ecommerce_entitlement(self.request.site.partner, course, entitlement, partial=True)

        return Response(serializer.data)

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
        return super(CourseViewSet, self).retrieve(request, *args, **kwargs)
