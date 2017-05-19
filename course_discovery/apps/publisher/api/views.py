import logging

from dal import autocomplete
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from guardian.shortcuts import get_objects_for_user
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.api.permissions import (CanViewAssociatedCourse, InternalUserPermission,
                                                             PublisherUserPermission)
from course_discovery.apps.publisher.api.serializers import (CourseRevisionSerializer, CourseRunSerializer,
                                                             CourseRunStateSerializer, CourseStateSerializer,
                                                             CourseUserRoleSerializer, GroupUserSerializer)
from course_discovery.apps.publisher.forms import CustomCourseForm
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension)
from course_discovery.apps.publisher.utils import is_internal_user, is_publisher_admin

logger = logging.getLogger(__name__)

historicalcourse = apps.get_model('publisher', 'historicalcourse')


class CourseRoleAssignmentView(UpdateAPIView):
    """ Update view for CourseUserRole """
    permission_classes = (IsAuthenticated, CanViewAssociatedCourse,)
    queryset = CourseUserRole.objects.all()
    serializer_class = CourseUserRoleSerializer


class OrganizationGroupUserView(ListAPIView):
    """ List view for Users filtered by group """
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        org_extension = get_object_or_404(OrganizationExtension, organization=self.kwargs.get('pk'))
        queryset = User.objects.filter(groups__name=org_extension.group).order_by('full_name', 'username')
        return queryset


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

    def put(self, request, history_id):  # pylint: disable=unused-argument
        """ Update the course version against the given revision id. """
        history_object = get_object_or_404(historicalcourse, pk=history_id)
        course = get_object_or_404(Course, id=history_object.id)
        try:
            for field in CustomCourseForm().fields:
                if field not in ['team_admin', 'organization', 'add_new_run']:
                    setattr(course, field, getattr(history_object, field))

            course.changed_by = self.request.user
            course.save()
        except:  # pylint: disable=bare-except
            logger.exception('Unable to revert the course [%s] for revision [%s].', course.id, history_id)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CoursesAutoComplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """ Course Autocomplete. """

    def get_queryset(self):
        if self.q:
            user = self.request.user
            if is_publisher_admin(user):
                qs = Course.objects.filter(title__icontains=self.q)
            elif is_internal_user(user):
                qs = Course.objects.filter(title__icontains=self.q, course_user_roles__user=user).distinct()
            else:
                organizations = get_objects_for_user(
                    user,
                    OrganizationExtension.VIEW_COURSE,
                    OrganizationExtension,
                    use_groups=True,
                    with_superuser=False
                ).values_list('organization')
                qs = Course.objects.filter(title__icontains=self.q, organizations__in=organizations)

            return qs

        return []


class AcceptAllRevisionView(APIView):
    """ Generate history version. """
    permission_classes = (IsAuthenticated, )

    def post(self, request, history_id):  # pylint: disable=unused-argument
        """ Update the course against the given revision id. """

        history_object = get_object_or_404(historicalcourse, pk=history_id)
        course = get_object_or_404(Course, id=history_object.id)

        course.changed_by = self.request.user
        course.save()

        return Response(status=status.HTTP_201_CREATED)
