from rest_framework.generics import UpdateAPIView, ListAPIView, get_object_or_404, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.api.permissions import (
    CanViewAssociatedCourse, InternalUserPermission, PublisherUserPermission
)
from course_discovery.apps.publisher.api.serializers import (
    CourseUserRoleSerializer, GroupUserSerializer, UpdateCourseKeySerializer, CourseRevisionSerializer,
    CourseStateSerializer
)
from course_discovery.apps.publisher.models import CourseUserRole, OrganizationExtension, CourseRun, CourseState, Course


class CourseRoleAssignmentView(UpdateAPIView):
    permission_classes = (IsAuthenticated, CanViewAssociatedCourse, InternalUserPermission,)
    queryset = CourseUserRole.objects.all()
    serializer_class = CourseUserRoleSerializer


class OrganizationGroupUserView(ListAPIView):
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        org_extension = get_object_or_404(OrganizationExtension, organization=self.kwargs.get('pk'))
        queryset = User.objects.filter(groups__name=org_extension.group)
        return queryset


class UpdateCourseKeyView(UpdateAPIView):
    permission_classes = (IsAuthenticated, InternalUserPermission,)
    queryset = CourseRun.objects.all()
    serializer_class = UpdateCourseKeySerializer


class CourseRevisionDetailView(RetrieveAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = CourseRevisionSerializer
    queryset = Course.history.all()  # pylint: disable=no-member
    lookup_field = 'history_id'


class ChangeCourseStateView(UpdateAPIView):
    permission_classes = (IsAuthenticated, PublisherUserPermission,)
    queryset = CourseState.objects.all()
    serializer_class = CourseStateSerializer
