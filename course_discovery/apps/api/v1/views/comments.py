import logging

from django.http.response import Http404
from django.utils.translation import ugettext as _
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api.serializers import CommentSerializer
from course_discovery.apps.core.models import SalesforceConfiguration
from course_discovery.apps.course_metadata.emails import send_email_for_comment
from course_discovery.apps.course_metadata.models import Course, CourseEditor, Organization
from course_discovery.apps.course_metadata.salesforce import SalesforceMissingCaseException, SalesforceUtil
from course_discovery.apps.course_metadata.utils import ensure_draft_world

log = logging.getLogger(__name__)


class CommentViewSet(viewsets.GenericViewSet):

    permission_classes = (IsAuthenticated,)
    serializer_class = CommentSerializer

    def get_queryset(self):
        """
        Override needed for DRF, but we don't use any queryset for this ViewSet
        """

    def list(self, request):
        course_uuid = request.query_params.get('course_uuid')
        if not course_uuid:
            return Response(
                _('You must include a course_uuid in your query parameters.'),
                status=status.HTTP_400_BAD_REQUEST
            )
        partner = request.site.partner
        course = self._get_course_or_404(partner, course_uuid)

        user_orgs = Organization.user_organizations(request.user)
        if not set(user_orgs).intersection(course.authoring_organizations.all()) and not request.user.is_staff:
            raise PermissionDenied

        util = self._get_salesforce_util_or_404(partner)
        comments = util.get_comments_for_course(course)

        return Response(comments)

    def create(self, request):
        comment_creation_fields = {
            'course_uuid': request.data.get('course_uuid'),
            'comment': request.data.get('comment'),
        }

        missing_values = [k for k, v in comment_creation_fields.items() if v is None]
        error_message = ''
        if missing_values:
            error_message += ''.join([_('Missing value for: [{name}]. ').format(name=name) for name in missing_values])
        if error_message:
            return Response((_('Incorrect data sent. ') + error_message).strip(), status=status.HTTP_400_BAD_REQUEST)

        partner = self.request.site.partner
        course = self._get_course_or_404(partner, comment_creation_fields.get('course_uuid'))

        if not CourseEditor.is_course_editable(request.user, course):
            raise PermissionDenied

        util = self._get_salesforce_util_or_404(partner)
        try:
            comment = util.create_comment_for_course_case(
                course,
                request.user,
                comment_creation_fields.get('comment'),
                course_run_key=request.data.get('course_run_key')
            )
            send_email_for_comment(comment, course, request.user)
            return Response(comment, status=status.HTTP_201_CREATED)
        except SalesforceMissingCaseException as ex:
            return Response(ex.message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def _get_course_or_404(partner, course_uuid):
        try:
            course = Course.objects.filter_drafts().get(partner=partner, uuid=course_uuid)
            return ensure_draft_world(course)
        except Course.DoesNotExist:
            raise Http404

    @staticmethod
    def _get_salesforce_util_or_404(partner):
        try:
            return SalesforceUtil(partner)
        except SalesforceConfiguration.DoesNotExist:
            raise Http404
