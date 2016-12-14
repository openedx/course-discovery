from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.publisher.models import CourseUserRole
from course_discovery.apps.publisher.api.permissions import CanViewAssociatedCourse, InternalUserPermission
from course_discovery.apps.publisher.api.serializers import CourseUserRoleSerializer


class CourseRoleAssignmentView(UpdateAPIView):
    permission_classes = (IsAuthenticated, CanViewAssociatedCourse, InternalUserPermission,)
    queryset = CourseUserRole.objects.all()
    serializer_class = CourseUserRoleSerializer
