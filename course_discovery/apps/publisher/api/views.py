from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.api.permissions import (CanViewAssociatedCourse, InternalUserPermission,
                                                             PublisherUserPermission)
from course_discovery.apps.publisher.api.serializers import (CourseRevisionSerializer, CourseRunSerializer,
                                                             CourseRunStateSerializer, CourseStateSerializer,
                                                             CourseUserRoleSerializer, GroupUserSerializer)
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseRunState, CourseState, CourseUserRole,
                                                    OrganizationExtension)


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
