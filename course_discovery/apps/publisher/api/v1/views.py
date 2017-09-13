import logging

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_framework_extensions.authentication import JwtAuthentication
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.models import CourseRun as DiscoveryCourseRun
from course_discovery.apps.course_metadata.models import Course, Video
from course_discovery.apps.publisher.models import CourseRun, Seat
from course_discovery.apps.publisher.studio_api_utils import StudioAPI

logger = logging.getLogger(__name__)


class CourseRunViewSet(viewsets.GenericViewSet):
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    lookup_url_kwarg = 'pk'
    queryset = CourseRun.objects.all()
    # NOTE: We intentionally use a basic serializer here since there is nothing, yet, to return.
    serializer_class = serializers.Serializer
    permission_classes = (permissions.IsAdminUser,)

    @detail_route(methods=['post'])
    def publish(self, request, pk=None):
        course_run = self.get_object()
        partner = request.site.partner

        try:
            self.publish_to_studio(partner, course_run)
            self.publish_to_ecommerce(partner, course_run)
            self.publish_to_discovery(partner, course_run)
        except SlumberBaseException as ex:
            logger.exception('Failed to publish course run [%s]!', pk)
            content = getattr(ex, 'content', None)
            if content:
                logger.error(content)
            raise

        return Response({}, status=status.HTTP_200_OK)

    def publish_to_studio(self, partner, course_run):
        api = StudioAPI(partner.studio_api_client)
        api.update_course_run_details_in_studio(course_run)
        api.update_course_run_image_in_studio(course_run)

    def publish_to_ecommerce(self, partner, course_run):
        api = EdxRestApiClient(partner.ecommerce_api_url, jwt=partner.access_token)
        data = {
            'id': course_run.lms_course_id,
            'name': course_run.title_override or course_run.course.title,
            'verification_deadline': None,
            'create_or_activate_enrollment_code': False,
            'products': [
                {
                    'expires': serialize_datetime(seat.upgrade_deadline),
                    'price': str(seat.price),
                    'product_class': 'Seat',
                    'attribute_values': [
                        {
                            'name': 'certificate_type',
                            'value': None if seat.type is Seat.AUDIT else seat.type,
                        },
                        {
                            'name': 'id_verification_required',
                            'value': seat.type in (Seat.VERIFIED, Seat.PROFESSIONAL),
                        }
                    ]
                } for seat in course_run.seats.all()
            ]
        }
        api.publication.post(data)

    def publish_to_discovery(self, partner, course_run):
        publisher_course = course_run.course
        course_key = '{org}+{number}'.format(org=publisher_course.organizations.first().key,
                                             number=publisher_course.number)

        video = None
        if publisher_course.video_link:
            video, __ = Video.objects.get_or_create(src=publisher_course.video_link)

        # TODO Host card images from the Discovery Service CDN
        defaults = {
            'title': publisher_course.title,
            'short_description': publisher_course.short_description,
            'full_description': publisher_course.full_description,
            'level_type': publisher_course.level_type,
            'video': video,
        }
        discovery_course, created = Course.objects.update_or_create(partner=partner, key=course_key, defaults=defaults)
        discovery_course.authoring_organizations.add(*publisher_course.organizations.all())

        subjects = [subject for subject in set([
            publisher_course.primary_subject,
            publisher_course.secondary_subject,
            publisher_course.tertiary_subject
        ]) if subject]
        discovery_course.subjects.add(*subjects)

        defaults = {
            'start': course_run.start,
            'end': course_run.end,
            'enrollment_start': course_run.enrollment_start,
            'enrollment_end': course_run.enrollment_end,
            'pacing_type': course_run.pacing_type,
            'title_override': course_run.title_override,
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'language': course_run.language,

        }
        discovery_course_run, __ = DiscoveryCourseRun.objects.update_or_create(
            course=discovery_course,
            key=course_run.lms_course_id,
            defaults=defaults
        )
        discovery_course_run.transcript_languages.add(*course_run.transcript_languages.all())

        if created:
            discovery_course.canonical_course_run = discovery_course_run
            discovery_course.save()
