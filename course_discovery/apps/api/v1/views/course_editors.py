from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import CursorPagination

from course_discovery.apps.api.filters import CourseEditorFilter
from course_discovery.apps.api.permissions import CanAppointCourseEditor
from course_discovery.apps.api.serializers import CourseEditorSerializer
from course_discovery.apps.course_metadata.models import Course, CourseEditor


class CourseEditorViewSet(mixins.CreateModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.ListModelMixin,
                          mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    """CourseEditor Resource"""
    permission_classes = [CanAppointCourseEditor]
    serializer_class = CourseEditorSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CourseEditorFilter
    pagination_class = CursorPagination

    @property
    def course(self):
        return Course.objects.filter_drafts(uuid=self.request.data['course'], partner=self.request.site.partner).first()

    def get_queryset(self):
        return CourseEditor.editors_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        """The User who performs creation must be staff or belonging to the associated organization, the user being
        assigned must belong to the associated organization"""
        if 'user_id' not in request.data:
            request.data['user_id'] = request.user.id

        user_model = get_user_model()
        editor = get_object_or_404(user_model, pk=request.data['user_id'])
        authoring_orgs = self.course.authoring_organizations.all()
        users_in_authoring_orgs = user_model.objects.filter(
            groups__organization_extension__organization__in=authoring_orgs
        ).distinct()

        if editor not in users_in_authoring_orgs:
            raise PermissionDenied('Editor does not belong to an authoring organization of this course.')

        return super().create(request)
