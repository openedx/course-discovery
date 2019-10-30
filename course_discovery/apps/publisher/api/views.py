import logging
import re

from dal import autocomplete
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView, get_object_or_404
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.api.filters import OrganizationUserRoleFilterSet
from course_discovery.apps.publisher.api.paginations import LargeResultsSetPagination
from course_discovery.apps.publisher.api.permissions import (
    CanViewAssociatedCourse, InternalUserPermission, PublisherUserPermission
)
from course_discovery.apps.publisher.api.serializers import (
    CourseRevisionSerializer, CourseRunSerializer, CourseRunStateSerializer, CourseStateSerializer,
    CourseUserRoleSerializer, GroupUserSerializer, OrganizationUserRoleSerializer
)
from course_discovery.apps.publisher.forms import CourseForm
from course_discovery.apps.publisher.models import (
    Course, CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension, OrganizationUserRole,
    PublisherUser
)

logger = logging.getLogger(__name__)

historicalcourse = apps.get_model('publisher', 'historicalcourse')

id_regex = re.compile(r'\d+')


class CourseRoleAssignmentView(UpdateAPIView):
    """ Update view for CourseUserRole """
    permission_classes = (IsAuthenticated, CanViewAssociatedCourse,)
    queryset = CourseUserRole.objects.all()
    serializer_class = CourseUserRoleSerializer


class OrganizationUserRoleView(ListAPIView):
    """ List view for OrganizationUserRole """
    filter_backends = (DjangoFilterBackend,)
    filterset_class = OrganizationUserRoleFilterSet
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, PublisherUserPermission)
    serializer_class = OrganizationUserRoleSerializer

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        lookup = {'organization': pk} if id_regex.fullmatch(pk) else {'organization__uuid': pk}
        return OrganizationUserRole.objects.filter(**lookup)


class OrganizationGroupUserView(ListAPIView):
    """ List view for Users filtered by group """
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated, PublisherUserPermission)
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        lookup = {'organization': pk} if id_regex.fullmatch(pk) else {'organization__uuid': pk}
        org_extension = get_object_or_404(OrganizationExtension, **lookup)
        return User.objects.filter(groups__organization_extension=org_extension).order_by('full_name', 'username')


class OrganizationUserView(ListAPIView):
    """ List view for all users in requester's organizations """
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated, PublisherUserPermission)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            partner = self.request.site.partner
            organization_extensions = OrganizationExtension.objects.filter(organization__partner=partner)
            return User.objects.filter(
                groups__organization_extension__in=organization_extensions).distinct().order_by('full_name')

        return User.objects.filter(
            groups__organization_extension__group__in=user.groups.all()).distinct().order_by('full_name')


class UpdateCourseRunView(UpdateAPIView):
    """ Update view for CourseRuns """
    permission_classes = (IsAuthenticated, InternalUserPermission,)
    queryset = CourseRun.objects.all()
    serializer_class = CourseRunSerializer


class CourseRevisionDetailView(RetrieveAPIView):
    """ Retrieve view for Course revision history """
    permission_classes = (IsAuthenticated, )
    serializer_class = CourseRevisionSerializer
    queryset = Course.history.all()  # pylint: disable=no-member
    lookup_field = 'history_id'


class ChangeCourseStateView(UpdateAPIView):
    """ Update view for CourseStates """
    permission_classes = (IsAuthenticated, PublisherUserPermission,)
    queryset = CourseState.objects.all()
    serializer_class = CourseStateSerializer


class ChangeCourseRunStateView(UpdateAPIView):
    """ Update view for CourseRunStates """
    permission_classes = (IsAuthenticated, PublisherUserPermission,)
    queryset = CourseRunState.objects.all()
    serializer_class = CourseRunStateSerializer


class RevertCourseRevisionView(APIView):
    """ Revert view for Course against a history version """
    permission_classes = (IsAuthenticated, )

    def put(self, _request, history_id):
        """ Update the course version against the given revision id. """
        history_object = get_object_or_404(historicalcourse, pk=history_id)
        course = get_object_or_404(Course, id=history_object.id)
        try:
            for field in CourseForm().fields:
                if field not in ['team_admin', 'organization', 'add_new_run', 'url_slug']:
                    setattr(course, field, getattr(history_object, field))

            course.changed_by = self.request.user
            course.save()
        except Exception:  # pylint: disable=broad-except
            logger.exception('Unable to revert the course [%s] for revision [%s].', course.id, history_id)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CoursesAutoComplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """ Course Autocomplete. """

    def get_results(self, context):
        """
        Format the result set so that it can be returned as a JSON object.

        Overridden from https://github.com/yourlabs/django-autocomplete-light/blob/3.1.8/src/dal_select2/views.py#L14
        to include information about whether or not the suggested Course(s) use entitlements.
        """
        return [
            {
                'id': self.get_result_value(course),
                'text': self.get_result_label(course),
                'uses_entitlements': course.uses_entitlements
            } for course in context['object_list']
        ]

    def get_queryset(self):
        if self.q:
            qs = PublisherUser.get_courses(self.request.user)
            return qs.filter(title__icontains=self.q)

        return []


class AcceptAllRevisionView(APIView):
    """ Generate history version. """
    permission_classes = (IsAuthenticated, )

    def post(self, _request, history_id):
        """ Update the course against the given revision id. """

        history_object = get_object_or_404(historicalcourse, pk=history_id)
        course = get_object_or_404(Course, id=history_object.id)

        course.changed_by = self.request.user
        course.save()

        return Response(status=status.HTTP_201_CREATED)
