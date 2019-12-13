import logging
from datetime import date

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from requests import RequestException
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from course_discovery.apps.course_metadata.utils import push_to_ecommerce_for_course_run
from course_discovery.apps.publisher.models import CourseRun
from course_discovery.apps.publisher.studio_api_utils import StudioAPI

logger = logging.getLogger(__name__)


class CourseRunViewSet(viewsets.GenericViewSet):
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    queryset = CourseRun.objects.all()
    # NOTE: We intentionally use a basic serializer here since there is nothing, yet, to return.
    serializer_class = serializers.Serializer
    permission_classes = (permissions.IsAdminUser,)

    PUBLICATION_SUCCESS_STATUS = 'SUCCESS'

    @action(detail=True, methods=['post'])
    def publish(self, request, **_kwargs):
        course_run = self.get_object()
        partner = request.site.partner

        publication_status = {
            'studio': self.publish_to_studio(partner, course_run),
            'discovery': self.publish_to_discovery(),
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
            course_run_response = api.push_to_studio(course_run)
        except SlumberBaseException as ex:
            content = ex.content.decode('utf8')
            logger.exception('Failed to publish course run [%d] to Studio! Error was: [%s]', course_run.pk, content)
            return 'FAILED: ' + content
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception('Failed to publish course run [%d] to Studio!', course_run.pk)
            return 'FAILED: ' + str(ex)

        api.update_course_run_image_in_studio(course_run, course_run_response)

        return self.PUBLICATION_SUCCESS_STATUS

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

    def publish_to_discovery(self):
        return self.PUBLICATION_SUCCESS_STATUS
