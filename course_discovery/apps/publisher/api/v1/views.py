import logging
from collections import OrderedDict
from datetime import date

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from requests import RequestException
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from course_discovery.apps.course_metadata.models import CourseEntitlement as DiscoveryCourseEntitlement
from course_discovery.apps.course_metadata.models import CourseRun as DiscoveryCourseRun
from course_discovery.apps.course_metadata.models import Seat as DiscoverySeat
from course_discovery.apps.course_metadata.models import Course, SeatType, Video
from course_discovery.apps.course_metadata.utils import push_to_ecommerce_for_course_run
from course_discovery.apps.publisher.models import CourseRun, Seat
from course_discovery.apps.publisher.studio_api_utils import StudioAPI
from course_discovery.apps.publisher.utils import get_course_key

logger = logging.getLogger(__name__)


class CourseRunViewSet(viewsets.GenericViewSet):
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    queryset = CourseRun.objects.all()
    # NOTE: We intentionally use a basic serializer here since there is nothing, yet, to return.
    serializer_class = serializers.Serializer
    permission_classes = (permissions.IsAdminUser,)

    PUBLICATION_SUCCESS_STATUS = 'SUCCESS'

    @detail_route(methods=['post'])
    def publish(self, request, **_kwargs):
        course_run = self.get_object()
        partner = request.site.partner

        publication_status = {
            'studio': self.publish_to_studio(partner, course_run),
            'discovery': self.publish_to_discovery(partner, course_run),
            # Publish to ecommerce last because it needs the just-created UUID from discovery
            'ecommerce': self.publish_to_ecommerce(course_run),
        }

        status_code = status.HTTP_200_OK
        for _status in publication_status.values():
            if not _status.startswith(self.PUBLICATION_SUCCESS_STATUS):
                status_code = status.HTTP_502_BAD_GATEWAY
                break
        if status_code == status.HTTP_200_OK:
            logger.info(
                'Published course run with id: [%d] lms_course_id: [%s], user: [%s], date: [%s]',
                course_run.id,
                course_run.lms_course_id,
                request.user,
                date.today()
            )
        return Response(publication_status, status=status_code)

    def publish_to_studio(self, partner, course_run):
        api = StudioAPI(partner.studio_api_client)

        try:
            api.push_to_studio(course_run)
            return self.PUBLICATION_SUCCESS_STATUS
        except SlumberBaseException as ex:
            content = ex.content.decode('utf8')
            logger.exception('Failed to publish course run [%d] to Studio! Error was: [%s]', course_run.pk, content)
            return 'FAILED: ' + content
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception('Failed to publish course run [%d] to Studio!', course_run.pk)
            return 'FAILED: ' + str(ex)

    def publish_to_ecommerce(self, course_run):
        discovery_run = course_run.discovery_course_run
        try:
            push_to_ecommerce_for_course_run(discovery_run)
            return self.PUBLICATION_SUCCESS_STATUS
        except RequestException as ex:
            text = str(ex) if ex.response is None else ex.response.text
            logger.exception('Failed to publish course run [%d] to E-Commerce! Error was: [%s]', course_run.id, text)
            return 'FAILED: ' + text
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception('Failed to publish course run [%d] to E-Commerce!', course_run.pk)
            return 'FAILED: ' + str(ex)

    def publish_to_discovery(self, partner, course_run):
        publisher_course = course_run.course
        course_key = get_course_key(publisher_course)

        video = None
        if publisher_course.video_link:
            video, __ = Video.objects.get_or_create(src=publisher_course.video_link)

        defaults = {
            'title': publisher_course.title,
            'short_description': publisher_course.short_description,
            'full_description': publisher_course.full_description,
            'level_type': publisher_course.level_type,
            'video': video,
            'outcome': publisher_course.expected_learnings,
            'prerequisites_raw': publisher_course.prerequisites,
            'syllabus_raw': publisher_course.syllabus,
            'additional_information': publisher_course.additional_information,
            'faq': publisher_course.faq,
            'learner_testimonials': publisher_course.learner_testimonial,
        }
        discovery_course, created = Course.objects.update_or_create(partner=partner, key=course_key, defaults=defaults)
        discovery_course.image.save(publisher_course.image.name, publisher_course.image.file)
        discovery_course.authoring_organizations.add(*publisher_course.organizations.all())

        subjects = [subject for subject in [
            publisher_course.primary_subject,
            publisher_course.secondary_subject,
            publisher_course.tertiary_subject
        ] if subject]
        subjects = list(OrderedDict.fromkeys(subjects))
        discovery_course.subjects.clear()
        discovery_course.subjects.add(*subjects)

        defaults = {
            'start': course_run.start_date_temporary,
            'end': course_run.end_date_temporary,
            'pacing_type': course_run.pacing_type_temporary,
            'title_override': course_run.title_override,
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'language': course_run.language,
            'weeks_to_complete': course_run.length,
            'has_ofac_restrictions': course_run.has_ofac_restrictions
        }
        discovery_course_run, __ = DiscoveryCourseRun.objects.update_or_create(
            course=discovery_course,
            key=course_run.lms_course_id,
            defaults=defaults
        )
        discovery_course_run.transcript_languages.add(*course_run.transcript_languages.all())
        discovery_course_run.staff.clear()
        discovery_course_run.staff.add(*course_run.staff.all())

        for entitlement in publisher_course.entitlements.all():
            DiscoveryCourseEntitlement.objects.update_or_create(
                course=discovery_course,
                mode=SeatType.objects.get(slug=entitlement.mode),
                defaults={
                    'partner': partner,
                    'price': entitlement.price,
                    'currency': entitlement.currency,
                }
            )

        for seat in course_run.seats.exclude(type=Seat.CREDIT).order_by('created'):
            DiscoverySeat.objects.update_or_create(
                course_run=discovery_course_run,
                type=seat.type,
                currency=seat.currency,
                defaults={
                    'price': seat.price,
                    'upgrade_deadline': seat.calculated_upgrade_deadline,
                }
            )
            if seat.masters_track:
                DiscoverySeat.objects.update_or_create(
                    course_run=discovery_course_run,
                    type=DiscoverySeat.MASTERS,
                    currency=seat.currency,
                    defaults={
                        'price': seat.price,
                        'upgrade_deadline': seat.calculated_upgrade_deadline,
                    }
                )

        if created:
            discovery_course.canonical_course_run = discovery_course_run
            discovery_course.save()

        return self.PUBLICATION_SUCCESS_STATUS
